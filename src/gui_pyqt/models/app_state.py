"""
PresidioPDF PyQt - アプリケーション状態管理

Phase 1: 基本状態管理
- 現在のPDFファイルパス
- read結果（JSON）
- detect結果（JSON）
"""

from pathlib import Path
from typing import Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal


class AppState(QObject):
    """アプリケーション状態を一元管理するクラス"""

    # シグナル定義
    pdf_path_changed = pyqtSignal(object)  # Optional[Path]
    read_result_changed = pyqtSignal(object)  # Optional[dict]
    detect_result_changed = pyqtSignal(object)  # Optional[dict]
    duplicate_result_changed = pyqtSignal(object)  # Optional[dict]
    status_message_changed = pyqtSignal(str)  # ステータスメッセージ

    def __init__(self):
        super().__init__()
        self._pdf_path: Optional[Path] = None
        self._read_result: Optional[dict] = None
        self._detect_result: Optional[dict] = None
        self._duplicate_result: Optional[dict] = None
        self._status_message: str = "準備完了"

    @property
    def pdf_path(self) -> Optional[Path]:
        """現在のPDFファイルパス"""
        return self._pdf_path

    @pdf_path.setter
    def pdf_path(self, value: Optional[Path]):
        """PDFファイルパスを設定"""
        if self._pdf_path != value:
            self._pdf_path = value
            self.pdf_path_changed.emit(value)
            if value:
                self.status_message = f"PDFを選択: {value.name}"
            else:
                self.status_message = "PDFが未選択"

    @property
    def read_result(self) -> Optional[dict]:
        """read処理の結果（JSON）"""
        return self._read_result

    @read_result.setter
    def read_result(self, value: Optional[dict]):
        """read結果を設定"""
        if self._read_result != value:
            self._read_result = value
            self.read_result_changed.emit(value)
            if value:
                self.status_message = "Read処理が完了しました"

    @property
    def detect_result(self) -> Optional[dict]:
        """detect処理の結果（JSON）"""
        return self._detect_result

    @detect_result.setter
    def detect_result(self, value: Optional[dict]):
        """detect結果を設定"""
        if self._detect_result != value:
            self._detect_result = value
            self.detect_result_changed.emit(value)
            if value:
                self.status_message = "Detect処理が完了しました"

    @property
    def duplicate_result(self) -> Optional[dict]:
        """duplicate処理の結果（JSON）"""
        return self._duplicate_result

    @duplicate_result.setter
    def duplicate_result(self, value: Optional[dict]):
        """duplicate結果を設定"""
        if self._duplicate_result != value:
            self._duplicate_result = value
            self.duplicate_result_changed.emit(value)
            if value:
                self.status_message = "Duplicate処理が完了しました"

    @property
    def status_message(self) -> str:
        """ステータスメッセージ"""
        return self._status_message

    @status_message.setter
    def status_message(self, value: str):
        """ステータスメッセージを設定"""
        if self._status_message != value:
            self._status_message = value
            self.status_message_changed.emit(value)

    def clear(self):
        """全ての状態をクリア"""
        self.pdf_path = None
        self.read_result = None
        self.detect_result = None
        self.duplicate_result = None
        self.status_message = "準備完了"

    def has_pdf(self) -> bool:
        """PDFが選択されているか"""
        return self._pdf_path is not None

    def has_read_result(self) -> bool:
        """read結果が存在するか"""
        return self._read_result is not None

    def has_detect_result(self) -> bool:
        """detect結果が存在するか"""
        return self._detect_result is not None

    def has_duplicate_result(self) -> bool:
        """duplicate結果が存在するか"""
        return self._duplicate_result is not None
