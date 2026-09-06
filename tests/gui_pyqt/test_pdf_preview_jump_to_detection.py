"""右ペイン（結果一覧）でのエンティティ選択時に、左ペイン（PDFプレビュー）が
検出位置のページへ切り替わり、その矩形がビューポート中央付近へスクロールされる
ことを検証する退行テスト。

対象: PDFPreviewWidget.jump_to_detection（縦横ともに中央寄せでスクロールする）。
テストPDF harumichi.pdf は複数ページにわたって検出位置が散らばっており、
2ページ目（page_index=1）のページ下寄りの単語をスクロール対象として使う。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pytest
from PyQt6.QtWidgets import QApplication

from src.gui_pyqt.views.pdf_preview import PDFPreviewWidget

HARUMICHI_PDF = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "test_pdfs",
    "harumichi.pdf",
)

TARGET_PAGE_INDEX = 1


@pytest.fixture(scope="module")
def _qapp():
    return QApplication.instance() or QApplication([])


def _find_target_word_rect(pdf_path: str, page_index: int) -> list:
    """テスト対象PDFのpage_index内から、ページ下寄りの単語矩形を1つ取得する。"""
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_index]
        words = page.get_text("words")
        # y0が最大（最もページ下方）の単語を選ぶ＝スクロールが必要な典型例
        target = max(words, key=lambda w: w[1])
        return [target[0], target[1], target[2], target[3]]
    finally:
        doc.close()


@pytest.fixture()
def preview_widget(_qapp):
    widget = PDFPreviewWidget()
    widget.resize(400, 300)
    widget.show()
    widget.load_pdf(HARUMICHI_PDF)
    _qapp.processEvents()
    try:
        yield widget
    finally:
        widget.close()


def test_jump_to_detection_switches_page(preview_widget, _qapp):
    """ページが異なる検出位置へジャンプすると、current_page_numが切り替わる。"""
    assert preview_widget.current_page_num == 0

    rect = _find_target_word_rect(HARUMICHI_PDF, TARGET_PAGE_INDEX)
    preview_widget.jump_to_detection(TARGET_PAGE_INDEX, rects_pdf=[rect])
    _qapp.processEvents()
    _qapp.processEvents()

    assert preview_widget.current_page_num == TARGET_PAGE_INDEX


def test_jump_to_detection_centers_rect_vertically_and_horizontally(preview_widget, _qapp):
    """スクロール後、対象矩形の中心がビューポート中央付近（クランプ後）に来る。"""
    rect = _find_target_word_rect(HARUMICHI_PDF, TARGET_PAGE_INDEX)
    preview_widget.jump_to_detection(TARGET_PAGE_INDEX, rects_pdf=[rect])
    _qapp.processEvents()
    _qapp.processEvents()

    scale = preview_widget.zoom_level * 2
    center_x_view = (rect[0] + rect[2]) / 2.0 * scale
    center_y_view = (rect[1] + rect[3]) / 2.0 * scale

    viewport = preview_widget.scroll_area.viewport()
    v_bar = preview_widget.scroll_area.verticalScrollBar()
    h_bar = preview_widget.scroll_area.horizontalScrollBar()

    expected_v = max(
        v_bar.minimum(),
        min(int(center_y_view - viewport.height() / 2), v_bar.maximum()),
    )
    expected_h = max(
        h_bar.minimum(),
        min(int(center_x_view - viewport.width() / 2), h_bar.maximum()),
    )

    # スクロール範囲は実際のレイアウト確定後の値に依存するため、若干の許容誤差を持たせる
    assert abs(v_bar.value() - expected_v) <= 2
    assert abs(h_bar.value() - expected_h) <= 2

    # ページが十分縦長であれば（本PDFはA4）、単純に「先頭に少しだけスクロール」
    # ではなく、実際に中央寄せが働いていること（0より十分大きい）も確認する
    if v_bar.maximum() > viewport.height():
        assert v_bar.value() > 0


def test_jump_to_detection_no_rect_still_switches_page(preview_widget, _qapp):
    """矩形情報が無くてもページ切り替え自体は行われる（フォールバック）。"""
    preview_widget.jump_to_detection(TARGET_PAGE_INDEX, rects_pdf=None, mask_circles_pdf=None)
    _qapp.processEvents()

    assert preview_widget.current_page_num == TARGET_PAGE_INDEX
