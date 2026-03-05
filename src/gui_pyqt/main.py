"""
PresidioPDF PyQt版 - メインエントリポイント

Phase 1: アプリ骨格（JusticePDF準拠）
- QApplicationの起動
- アプリ状態管理の初期化
- メインウィンドウの表示
"""

import sys

# Windows環境でPyQt6とonnxruntimeのDLL衝突を回避するため、
# PyQt6より先にonnxruntimeとcv2をインポートする。
# ndlocr-liteはオプション依存のためインポート失敗は無視する。
try:
    import onnxruntime  # noqa: F401
    import cv2  # noqa: F401
except ImportError:
    pass

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
