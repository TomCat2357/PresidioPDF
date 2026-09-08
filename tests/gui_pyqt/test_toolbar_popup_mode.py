"""回帰テスト: ツールバーの「ファイル」ボタンが、他の「処理」「OCR」「ヘルプ」ボタンと
同じくクリックでメニューが開くだけの InstantPopup になっていること。

以前は MenuButtonPopup + 表示専用アクションで、ボタン本体クリックが
「開く」の1クリック実行を兼ねており、押し間違えの原因になっていた。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QToolButton

from src.gui_pyqt.models.app_state import AppState
from src.gui_pyqt.views.main_window import MainWindow

from tests.gui_pyqt.test_pdf_switch_clears_manual_marks import (
    _FakeDetectConfigService,
)


def test_file_button_is_instant_popup_like_other_toolbar_buttons(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "src.gui_pyqt.views.main_window.DetectConfigService",
        _FakeDetectConfigService,
    )

    window = MainWindow(AppState())
    window.show()
    try:
        assert (
            window.file_button.popupMode()
            == QToolButton.ToolButtonPopupMode.InstantPopup
        )
        # 「処理」「OCR」「ヘルプ」と同じ挙動であることも確認する。
        assert (
            window.processing_button.popupMode()
            == QToolButton.ToolButtonPopupMode.InstantPopup
        )
        assert (
            window.ocr_button.popupMode() == QToolButton.ToolButtonPopupMode.InstantPopup
        )
        assert (
            window.help_button.popupMode()
            == QToolButton.ToolButtonPopupMode.InstantPopup
        )

        # 表示専用アクションは廃止され、ボタンのテキストは直接設定されている。
        assert window.file_button.text() == "ファイル"
        assert not hasattr(window, "file_default_action")

        # Ctrl+O のショートカットは open_action 経由で引き続き機能する。
        assert window.open_action.shortcut().toString() == "Ctrl+O"
        assert window.open_action in window.actions()
    finally:
        window._set_dirty(False)
        window.close()
