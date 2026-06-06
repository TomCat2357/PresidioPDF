"""GUIプレビューの文字→ブロック採番が、検出/マスク側の正準採番と一致することの退行テスト。

不具合の再現条件：表の空セル（空白のみのブロック）が存在すると、
- 検出/マスク側 `PDFBlockTextMapper._extract_page_blocks` は空白のみブロックを採番しない
- 旧 GUI `PDFPreviewWidget._get_page_chars` は採番してしまう（+1 ずれる）
ため、文字列ドラッグで手動選択したエンティティの `block_num` がずれ、
マスク時に隣の行へあふれて「変なところ」がマスクされていた。
本テストは両者の採番が一致することを保証する。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pytest
from PyQt6.QtWidgets import QApplication

from src.gui_pyqt.views.pdf_preview import PDFPreviewWidget
from src.pdf.pdf_block_mapper import PDFBlockTextMapper


def _make_pdf_with_empty_block(path):
    """住所行の前に空白のみブロックが来る合成PDFを作成する。"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Header")
    page.insert_text((72, 100), "   ")  # 空白のみ＝空セル相当（検出側はスキップする）
    page.insert_text((72, 130), "Address12345")
    page.insert_text((72, 160), "Row")
    doc.save(path)
    doc.close()


def _raw_blocks_with_lines(doc, page_num=0):
    rd = doc[page_num].get_text("rawdict")
    return [b for b in rd.get("blocks", []) if "lines" in b]


@pytest.fixture(scope="module")
def _qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def empty_block_pdf(tmp_path):
    path = str(tmp_path / "empty_block.pdf")
    _make_pdf_with_empty_block(path)

    # フィクスチャが本当に「空白のみブロック」を生むことを保証（PyMuPDFのバージョン差対策）。
    # 生まないと off-by-one が再現せず、テストが意味を持たないためスキップする。
    doc = fitz.open(path)
    raw_count = len(_raw_blocks_with_lines(doc))
    canon_count = len(PDFBlockTextMapper(fitz.open(path)).get_page_block_texts(0))
    doc.close()
    if raw_count <= canon_count:
        pytest.skip(
            "合成PDFが空白のみブロックを生成しなかったため、off-by-one を再現できない"
        )
    return path


def _gui_chars(pdf_path):
    widget = PDFPreviewWidget()
    try:
        widget.pdf_document = fitz.open(pdf_path)
        widget.current_page_num = 0
        widget._page_chars_cache = {}
        return widget._get_page_chars(0)
    finally:
        widget.close()


def test_gui_block_num_matches_canonical_for_every_char(_qapp, empty_block_pdf):
    """全選択文字について (gui_block_num, offset) が正準採番のテキストと一致する。"""
    chars = _gui_chars(empty_block_pdf)
    block_texts = PDFBlockTextMapper(fitz.open(empty_block_pdf)).get_page_block_texts(0)

    assert chars, "選択可能文字が1つも得られない"
    for c in chars:
        bn, off, ch = c["block_num"], c["offset"], c["char"]
        assert 0 <= bn < len(block_texts), f"block_num={bn} が正準ブロック範囲外"
        assert 0 <= off < len(block_texts[bn]), f"offset={off} がブロック範囲外 (block={bn})"
        assert block_texts[bn][off] == ch, (
            f"block={bn} offset={off}: GUI={ch!r} != 正準={block_texts[bn][off]!r}"
        )


def test_gui_distinct_block_count_equals_canonical(_qapp, empty_block_pdf):
    """GUI が見るブロック数 == 正準ブロック数（空白ブロックを多重計上していない）。"""
    chars = _gui_chars(empty_block_pdf)
    block_texts = PDFBlockTextMapper(fitz.open(empty_block_pdf)).get_page_block_texts(0)
    distinct = {c["block_num"] for c in chars}
    assert len(distinct) == len(block_texts)


def test_address_char_is_not_off_by_one(_qapp, empty_block_pdf):
    """住所先頭文字の block_num が、住所を含む正準ブロックを指す（隣の +1 ブロックでない）。"""
    chars = _gui_chars(empty_block_pdf)
    block_texts = PDFBlockTextMapper(fitz.open(empty_block_pdf)).get_page_block_texts(0)

    address_chars = [c for c in chars if c["char"] == "A"]
    assert address_chars, "住所文字 'A' が見つからない"
    bn = address_chars[0]["block_num"]
    assert "Address" in block_texts[bn], (
        f"住所先頭文字が block_num={bn} ({block_texts[bn]!r}) を指しており、住所ブロックでない"
    )
