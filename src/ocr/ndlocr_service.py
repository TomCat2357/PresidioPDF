"""後方互換シム。

NDLOCR-Lite は Python 3.14 移行に伴い撤去された（`numpy==2.2.2` 固定のため
cp314 wheel が無く 3.14 で導入不可）。OCR は RapidOCR v3
（``src/ocr/rapidocr_service.py`` の ``RapidOCRService``）に一本化されている。

本モジュールは旧 ``from src.ocr.ndlocr_service import OCRResult`` 形式の
import 互換のために ``OCRResult`` を再エクスポートするのみ。
"""

from src.ocr.base import OCRResult

__all__ = ["OCRResult"]
