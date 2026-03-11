import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.gui_pyqt.models.app_state import AppState
from src.gui_pyqt.views.main_window import MainWindow


class _FakeDetectConfigService:
    ENTITY_TYPES = ["PERSON"]
    ENTITY_ALIASES = {}
    DEFAULT_SPACY_MODEL = "ja_core_news_sm"
    DISPLAY_FILE_NAME = "config.json"

    def __init__(self, _home_path):
        pass

    def ensure_config_file(self):
        return ["PERSON"]

    def load_duplicate_settings(self):
        return {"entity_overlap_mode": "any", "overlap": "overlap"}

    def load_spacy_model(self):
        return self.DEFAULT_SPACY_MODEL

    def load_text_preprocess_settings(self):
        return {"ignore_newlines": True, "ignore_whitespace": False}

    def load_ocr_settings(self):
        return {
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


def test_preview_click_keeps_clicked_entity_selection(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "src.gui_pyqt.views.main_window.DetectConfigService",
        _FakeDetectConfigService,
    )

    window = MainWindow(AppState())
    try:
        assert app is not None
        window.show()
        visited_pages = []
        monkeypatch.setattr(
            window.pdf_preview,
            "go_to_page",
            lambda page: visited_pages.append(page),
        )

        window.app_state.detect_result = {
            "detect": [
                _make_entity("Alice", 0, 0, 0),
                _make_entity("Bob", 1, 0, 0),
            ]
        }
        app.processEvents()

        window.on_preview_entity_clicked(1)
        app.processEvents()

        assert window.result_panel.get_selected_entity_indices() == [1]
        assert visited_pages == [1]
    finally:
        window._set_dirty(False)
        window.close()
