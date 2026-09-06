import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


def _make_window_with_two_entities(monkeypatch):
    """Alice(page0)/Bob(page1)のエンティティを持つMainWindowを組み立てる共通処理"""
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "src.gui_pyqt.views.main_window.DetectConfigService",
        _FakeDetectConfigService,
    )

    window = MainWindow(AppState())
    window.show()
    # jump_to_detection はPDF読み込み済みであることを前提にページ範囲を判定するため、
    # ダミーのpdf_documentを設定しておく（実データ不要、len()が使えれば十分）。
    monkeypatch.setattr(
        window.pdf_preview,
        "pdf_document",
        [object(), object()],
    )

    window.app_state.detect_result = {
        "detect": [
            _make_entity("Alice", 0, 0, 0),
            _make_entity("Bob", 1, 0, 0),
        ]
    }
    app.processEvents()
    return app, window


def test_preview_click_keeps_clicked_entity_selection(monkeypatch):
    app, window = _make_window_with_two_entities(monkeypatch)
    try:
        visited_pages = []
        monkeypatch.setattr(
            window.pdf_preview,
            "go_to_page",
            lambda page: visited_pages.append(page),
        )

        window.on_preview_entity_clicked(1)
        app.processEvents()

        assert window.result_panel.get_selected_entity_indices() == [1]
        # プレビュー上のクリックは、クリックした位置が既にそのページ上にあるため
        # 追加のページ切り替えやスクロール（go_to_page/jump_to_detection）は
        # 発生しない（発生するとクリック位置から視点がズレて見えてしまう）。
        assert visited_pages == []
    finally:
        window._set_dirty(False)
        window.close()


def test_preview_click_does_not_trigger_jump_to_detection(monkeypatch):
    """プレビュー起点のクリックは jump_to_detection / go_to_page を呼ばない（回帰防止）"""
    app, window = _make_window_with_two_entities(monkeypatch)
    try:
        jump_calls = []
        go_to_page_calls = []
        monkeypatch.setattr(
            window.pdf_preview,
            "jump_to_detection",
            lambda *a, **k: jump_calls.append((a, k)),
        )
        monkeypatch.setattr(
            window.pdf_preview,
            "go_to_page",
            lambda page: go_to_page_calls.append(page),
        )

        window.on_preview_entity_clicked(1)
        app.processEvents()

        assert jump_calls == []
        assert go_to_page_calls == []
    finally:
        window._set_dirty(False)
        window.close()


def test_direct_entity_selected_triggers_jump_to_detection(monkeypatch):
    """ResultPanel側の選択変更（プレビュー起点でない）は jump_to_detection を呼ぶ"""
    app, window = _make_window_with_two_entities(monkeypatch)
    try:
        jump_calls = []
        monkeypatch.setattr(
            window.pdf_preview,
            "jump_to_detection",
            lambda *a, **k: jump_calls.append((a, k)),
        )

        # _suppress_preview_jump が立っていないことを前提に、直接 on_entity_selected を呼ぶ
        assert window._suppress_preview_jump is False
        window.on_entity_selected([_make_entity("Bob", 1, 0, 0)])
        app.processEvents()

        assert len(jump_calls) == 1
        assert jump_calls[0][0][0] == 1  # page_num引数
    finally:
        window._set_dirty(False)
        window.close()
