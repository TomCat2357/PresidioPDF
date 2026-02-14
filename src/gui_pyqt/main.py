"""
PresidioPDF PyQt版 - メインエントリポイント

Phase 1: アプリ骨格（JusticePDF準拠）
- QApplicationの起動
- アプリ状態管理の初期化
- メインウィンドウの表示
"""

import sys
from PyQt6.QtWidgets import QApplication

from .models.app_state import AppState
from .views.main_window import MainWindow


def main():
    """アプリケーションのエントリポイント"""
    # QApplicationの初期化
    app = QApplication(sys.argv)
    app.setApplicationName("PresidioPDF")
    app.setOrganizationName("PresidioPDF")

    # アプリケーション状態の作成
    app_state = AppState()

    # メインウィンドウを作成して表示
    window = MainWindow(app_state)
    window.show()

    # イベントループを開始
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
