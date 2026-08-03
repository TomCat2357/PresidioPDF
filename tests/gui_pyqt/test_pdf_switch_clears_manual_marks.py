"""回帰テスト: Detectを一度も実行せず手動でPIIマークだけした状態で
別のPDFを開いたとき、前のファイルの手動マークが残らないことを確認する。

バグの原因:
    AppStateの各setter（detect_result等）は「値が変化したときだけ」
    シグナルを発火する。手動マークのみの場合、detect_result/duplicate_result
    は一度もセットされずNoneのままなので、新しいPDFを開く際に
    `detect_result = None` を代入してもシグナルが発火せず、
    ResultPanelに前のPDFのマークが残り続けていた。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PyQt6.QtWidgets import QApplication

from src.gui_pyqt.models.app_state import AppState
from src.gui_pyqt.views.main_window import MainWindow


class _FakeDetectConfigService:
    ENTITY_TYPES = ["PERSON"]
    ENTITY_ALIASES = {}
    DEFAULT_SUDACHI_DICT_TYPE = "core"
    DEFAULT_SUDACHI_SPLIT_MODE = "C"
    DISPLAY_FILE_NAME = "config.json"

    def __init__(self, _home_path):
        pass

    def ensure_config_file(self):
        return ["PERSON"]

    def load_duplicate_settings(self):
        return {"entity_overlap_mode": "any", "overlap": "overlap"}

    def load_sudachi_settings(self):
        return {
            "dict_type": self.DEFAULT_SUDACHI_DICT_TYPE,
            "split_mode": self.DEFAULT_SUDACHI_SPLIT_MODE,
        }

    def load_text_preprocess_settings(self):
        return {"ignore_newlines": True, "ignore_whitespace": False}

    def load_ocr_settings(self):
        return {
            "backend": "rapidocr",
            "tier": "light",
            "font_color": [0, 0, 0],
            "opacity": 0.0,
            "ocr_before_detect": False,
            "auto_color": False,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }


def _make_entity(word: str, page_num: int, block_num: int, offset: int) -> dict:
    return {
        "word": word,
        "entity": "PERSON",
        "start": {"page_num": page_num, "block_num": block_num, "offset": offset},
        "end": {
            "page_num": page_num,
            "block_num": block_num,
            "offset": offset + len(word) - 1,
        },
    }


def _create_pdf(pdf_path, text):
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 120), text, fontsize=14)
        doc.save(str(pdf_path))


def test_opening_new_pdf_clears_manual_marks_when_detect_never_ran(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "src.gui_pyqt.views.main_window.DetectConfigService",
        _FakeDetectConfigService,
    )

    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _create_pdf(old_pdf, "旧ファイルの本文")
    _create_pdf(new_pdf, "新ファイルの本文")

    window = MainWindow(AppState())
    try:
        assert app is not None
        window.show()

        # マッピング読込・Read自動実行はバックグラウンドタスクを伴うためテストでは無効化する
        monkeypatch.setattr(window, "_load_mapping_for_pdf", lambda _p: False)
        monkeypatch.setattr(window, "_auto_read", lambda: None)

        # 1. old.pdfを開く
        window._open_pdf_path(old_pdf)
        app.processEvents()

        # 2. Detectは一度も実行せず、Read結果のみがある状態を再現する
        window.app_state.read_result = {
            "metadata": {"pdf": {"path": str(old_pdf)}},
            "text": [["旧ファイルの本文"]],
            "detect": [],
        }
        app.processEvents()

        # 3. 手動でPIIマークを追加する（ResultPanelへ直接反映し、AppStateへ書き戻す）
        manual_entity = _make_entity("旧ファイル", 0, 0, 0)
        window.result_panel.load_entities(
            {"detect": [manual_entity]}, owner_pdf_path=str(old_pdf)
        )
        window._update_app_state_from_result_panel()
        app.processEvents()

        # 前提確認: 手動マークが反映されており、Detect/Duplicateは未実行のまま
        assert window.result_panel.get_entities() == [manual_entity]
        assert window.app_state.detect_result is None
        assert window.app_state.duplicate_result is None
        assert window.app_state.read_result["detect"] == [manual_entity]

        # 4. 別のPDF（new.pdf）を開く
        window._open_pdf_path(new_pdf)
        app.processEvents()

        # 5. 前のPDFの手動マークがResultPanelに残っていないこと
        assert window.result_panel.get_entities() == []
        assert window.app_state.read_result is None
        assert window.app_state.detect_result is None
        assert window.app_state.duplicate_result is None

        # 6. Detect実行用の入力にも前PDFのマークが混入しないこと（二重防御の確認）
        detect_input = window._build_read_result_for_detect()
        assert detect_input.get("detect", []) == []
    finally:
        window._set_dirty(False)
        window.close()


def test_open_pdf_path_syncs_owner_pdf_path_to_new_pdf_via_auto_read(
    monkeypatch, tmp_path
):
    """新たなリグレッションの回帰テスト（owner_pdf_pathの更新順序）。

    _open_pdf_path()が「reset_results()を先に呼び、その後でpdf_pathを更新する」
    順序のままだと、reset_results()が発火するdetect_result_changedを購読する
    _refresh_result_view_from_state()の実行時点でapp_state.pdf_pathがまだ
    旧PDFのままとなり、ResultPanelのowner_pdf_pathに旧PDFのパスが
    刻まれて取り残されてしまう（マッピングが無く_auto_read経路に入った場合、
    以降ownerは更新されない）。

    PDF-Aへ手動マーク（Detect未実行）→ マッピングの無いPDF-Bを開く
    （_auto_read経路）という流れの直後で、ResultPanelのowner_pdf_pathが
    正しくPDF-Bへ更新されていることを確認する。
    """
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "src.gui_pyqt.views.main_window.DetectConfigService",
        _FakeDetectConfigService,
    )

    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    _create_pdf(pdf_a, "PDF-Aの本文")
    _create_pdf(pdf_b, "PDF-Bの本文")

    window = MainWindow(AppState())
    try:
        window.show()
        monkeypatch.setattr(window, "_load_mapping_for_pdf", lambda _p: False)
        monkeypatch.setattr(window, "_auto_read", lambda: None)

        # 1. PDF-Aを開いて手動マーク（Detect未実行）
        window._open_pdf_path(pdf_a)
        app.processEvents()
        window.app_state.read_result = {
            "metadata": {"pdf": {"path": str(pdf_a)}},
            "text": [["PDF-Aの本文"]],
            "detect": [],
        }
        entity_a = _make_entity("PDF-Aマーク", 0, 0, 0)
        window.result_panel.load_entities(
            {"detect": [entity_a]}, owner_pdf_path=str(pdf_a)
        )
        window._update_app_state_from_result_panel()
        app.processEvents()

        # 2. PDF-Bを開く（マッピング無し→_auto_read経路）
        window._open_pdf_path(pdf_b)
        app.processEvents()

        # 元バグ（前PDFのマークが残る）が再発していないことも併せて確認
        assert window.result_panel.get_entities() == []

        # 本題: owner_pdf_pathがPDF-Bへ正しく更新されていること
        # （更新順序に不備があると、ここがPDF-Aのパスのまま取り残される）
        assert window.result_panel.get_owner_pdf_path() == str(pdf_b)
    finally:
        window._set_dirty(False)
        window.close()


def test_manual_marks_on_second_pdf_survive_detect_after_auto_read_switch(
    monkeypatch, tmp_path
):
    """新たなリグレッションの回帰テスト（Detect実行時にマークが破棄されないこと）。

    PDF-Aへ手動マーク（Detect未実行）→ マッピングの無いPDF-Bを開く
    （_auto_read経路）→ PDF-Bへ手動マーク（この操作はload_entities()を
    経由せずentitiesへ直接追加されるため、owner_pdf_pathの更新はPDF-Bを
    開いた時点のものに依存する）→ 対象検出(Detect)実行、という流れで、
    PDF-Bの正当な手動マークが「別PDFのもの」と誤判定されて破棄されない
    ことを確認する。

    read_result側のdetectはあえてPDF-Bへの手動マークを反映しない状態
    （空のまま）にしておく。これはRead処理が非同期で走る実際のUIでは
    「PDF-Bを開いた直後、Readが完了する前にResultPanelへ手動マークが
    追加された」タイミングに相当し、_build_read_result_for_detect()が
    ResultPanel側のentities（フレッシュな値）を正しく採用できているかを
    read_result側へのフォールバックと区別して検証できる。
    もしowner_pdf_pathがPDF-Aのパスのまま取り残されていると、
    二重防御チェックが誤発火してResultPanel側のentitiesが破棄され、
    read_result側の空のdetectへフォールバックしてしまい、
    PDF-Bの正当な手動マークが消えてしまう。
    """
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "src.gui_pyqt.views.main_window.DetectConfigService",
        _FakeDetectConfigService,
    )

    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    _create_pdf(pdf_a, "PDF-Aの本文")
    _create_pdf(pdf_b, "PDF-Bの本文")

    window = MainWindow(AppState())
    try:
        window.show()
        monkeypatch.setattr(window, "_load_mapping_for_pdf", lambda _p: False)
        monkeypatch.setattr(window, "_auto_read", lambda: None)

        # 1. PDF-Aを開いて手動マーク（Detect未実行）
        window._open_pdf_path(pdf_a)
        app.processEvents()
        window.app_state.read_result = {
            "metadata": {"pdf": {"path": str(pdf_a)}},
            "text": [["PDF-Aの本文"]],
            "detect": [],
        }
        entity_a = _make_entity("PDF-Aマーク", 0, 0, 0)
        window.result_panel.load_entities(
            {"detect": [entity_a]}, owner_pdf_path=str(pdf_a)
        )
        window._update_app_state_from_result_panel()
        app.processEvents()

        # 2. PDF-Bを開く（マッピング無し→_auto_read経路）
        window._open_pdf_path(pdf_b)
        app.processEvents()

        # 元バグ（前PDFのマークが残る）が再発していないことも併せて確認
        assert window.result_panel.get_entities() == []

        # 3. PDF-BのRead結果は（まだ手動マークが反映されていない）空のdetectとし、
        #    ResultPanelにだけ手動マークを追加する（load_entities()を経由しない）。
        window.app_state.read_result = {
            "metadata": {"pdf": {"path": str(pdf_b)}},
            "text": [["PDF-Bの本文"]],
            "detect": [],
        }
        entity_b = _make_entity("PDF-Bマーク", 0, 0, 0)
        window.result_panel.entities = [entity_b]
        window.result_panel.update_table()
        app.processEvents()

        assert window.result_panel.get_entities() == [entity_b]

        # 4. 対象検出(Detect)実行用の入力を構築 -> PDF-Bの正当なマークが保持されること
        detect_input = window._build_read_result_for_detect()
        assert detect_input.get("detect", []) == [entity_b]
    finally:
        window._set_dirty(False)
        window.close()


def test_closing_pdf_clears_manual_marks_when_detect_never_ran(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "src.gui_pyqt.views.main_window.DetectConfigService",
        _FakeDetectConfigService,
    )

    pdf_path = tmp_path / "target.pdf"
    _create_pdf(pdf_path, "対象ファイルの本文")

    window = MainWindow(AppState())
    try:
        assert app is not None
        window.show()
        monkeypatch.setattr(window, "_load_mapping_for_pdf", lambda _p: False)
        monkeypatch.setattr(window, "_auto_read", lambda: None)

        window._open_pdf_path(pdf_path)
        app.processEvents()

        window.app_state.read_result = {
            "metadata": {"pdf": {"path": str(pdf_path)}},
            "text": [["対象ファイルの本文"]],
            "detect": [],
        }
        manual_entity = _make_entity("対象ファイル", 0, 0, 0)
        window.result_panel.load_entities(
            {"detect": [manual_entity]}, owner_pdf_path=str(pdf_path)
        )
        window._update_app_state_from_result_panel()
        app.processEvents()

        assert window.result_panel.get_entities() == [manual_entity]

        window.on_close_pdf()
        app.processEvents()

        assert window.result_panel.get_entities() == []
        assert window.app_state.pdf_path is None
    finally:
        window._set_dirty(False)
        window.close()
