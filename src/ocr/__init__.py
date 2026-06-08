"""OCR関連サービス。

OCR バックエンドは ``OCRBackend`` プロトコルで抽象化され、既定実装は
RapidOCR v3（``RapidOCRService``）。``get_ocr_service(settings)`` が config の
``ocr.tier`` に応じたバックエンドを返す。
"""

from typing import Any, Dict, Optional

from src.ocr.base import OCRBackend, OCRResult
from src.ocr.rapidocr_service import RapidOCRService

__all__ = [
    "OCRBackend",
    "OCRResult",
    "RapidOCRService",
    "get_ocr_service",
]


def get_ocr_service(ocr_settings: Optional[Dict[str, Any]] = None) -> OCRBackend:
    """config の OCR 設定からバックエンドを生成する。

    Args:
        ocr_settings: ``{"backend": "rapidocr", "tier": "light"|"heavy", ...}``

    Raises:
        RuntimeError: バックエンドが利用不可（依存未導入）の場合。
    """
    settings = ocr_settings or {}
    tier = str(settings.get("tier", "light") or "light")

    if not RapidOCRService.is_available():
        raise RuntimeError(
            "RapidOCR が利用できません。`uv sync --extra ocr` を実行してください。"
        )
    return RapidOCRService(tier=tier)
