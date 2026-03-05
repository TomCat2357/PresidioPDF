"""OCRテキスト埋め込みユーティリティ。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import fitz

from src.ocr.ndlocr_service import OCRResult

logger = logging.getLogger(__name__)


class PDFTextEmbedder:
    """OCR結果をPDFへ埋め込み・削除する。"""

    OCR_SUBJECT = "PresidioPDF_OCR"
    OCR_TITLE = "PresidioPDF OCR"
    OCR_SOURCE = "ndlocr-lite"

    @classmethod
    def embed_ocr_results(
        cls,
        doc: fitz.Document,
        ocr_results: Any,
        font_color: Sequence[float],
        opacity: float,
        auto_color: bool = False,
    ) -> int:
        """OCR結果をFreeText注釈として埋め込む。"""
        if not isinstance(doc, fitz.Document):
            raise TypeError("docはfitz.Documentである必要があります")

        global_text_color = cls._normalize_rgb_color(font_color)
        global_alpha = cls._clamp_opacity(opacity)
        inserted = 0
        for result in cls._iter_ocr_results(ocr_results):
            page_num = int(result.page_num)
            if page_num < 0 or page_num >= len(doc):
                continue
            page = doc[page_num]
            rect = fitz.Rect(
                float(result.x),
                float(result.y),
                float(result.x + result.width),
                float(result.y + result.height),
            )
            rect = rect & page.rect
            if not rect or rect.width <= 0.0 or rect.height <= 0.0:
                continue

            text = str(result.text or "").strip()
            if not text:
                continue

            if auto_color and result.text_color is not None:
                text_color = cls._normalize_rgb_color(result.text_color)
                alpha = cls._clamp_opacity(
                    result.text_opacity if result.text_opacity is not None else 1.0
                )
            else:
                text_color = global_text_color
                alpha = global_alpha

            fontsize = max(4.0, min(72.0, rect.height * 0.9))
            try:
                annot = page.add_freetext_annot(
                    rect,
                    text,
                    fontsize=fontsize,
                    fontname="helv",
                    text_color=text_color,
                    fill_color=None,
                    border_width=0,
                    opacity=alpha,
                    align=fitz.TEXT_ALIGN_LEFT,
                )
                annot.set_border(width=0)
                info = dict(annot.info or {})
                info["title"] = cls.OCR_TITLE
                info["subject"] = cls.OCR_SUBJECT
                if not str(info.get("content", "") or "").strip():
                    info["content"] = text
                annot.set_info(info)
                annot.update(opacity=alpha)
                inserted += 1
            except Exception as exc:
                logger.warning(
                    "OCRテキストの埋め込みに失敗: page=%s text=%s (%s)",
                    page_num,
                    text,
                    exc,
                )
                continue
        return inserted

    @classmethod
    def remove_ocr_text(
        cls,
        doc: fitz.Document,
        page_filter: Optional[Sequence[int]] = None,
    ) -> int:
        """埋め込んだOCRテキスト注釈を削除する。"""
        if not isinstance(doc, fitz.Document):
            raise TypeError("docはfitz.Documentである必要があります")

        target_pages = cls._resolve_target_pages(len(doc), page_filter)
        removed = 0
        for page_num in target_pages:
            page = doc[page_num]
            annot = page.first_annot
            while annot:
                next_annot = annot.next
                info = annot.info or {}
                subject = str(info.get("subject", "") or "")
                title = str(info.get("title", "") or "")
                content = str(info.get("content", "") or "")
                annot_type = annot.type[1] if isinstance(annot.type, tuple) else ""
                is_ocr = (
                    subject == cls.OCR_SUBJECT
                    or title == cls.OCR_TITLE
                    or f"source={cls.OCR_SOURCE}" in content
                )
                if is_ocr and str(annot_type).lower() == "freetext":
                    page.delete_annot(annot)
                    removed += 1
                annot = next_annot
        return removed

    @staticmethod
    def _clamp_opacity(value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = 0.0
        return min(1.0, max(0.0, parsed))

    @staticmethod
    def _normalize_rgb_color(color: Sequence[float]) -> Tuple[float, float, float]:
        if not isinstance(color, (list, tuple)) or len(color) < 3:
            return (0.0, 0.0, 0.0)
        try:
            channels = [float(color[0]), float(color[1]), float(color[2])]
        except (TypeError, ValueError):
            return (0.0, 0.0, 0.0)
        if any(channel > 1.0 for channel in channels):
            channels = [channel / 255.0 for channel in channels]
        return (
            min(1.0, max(0.0, channels[0])),
            min(1.0, max(0.0, channels[1])),
            min(1.0, max(0.0, channels[2])),
        )

    @classmethod
    def _iter_ocr_results(cls, ocr_results: Any) -> Iterable[OCRResult]:
        if isinstance(ocr_results, dict):
            for page_key, items in ocr_results.items():
                try:
                    page_num = int(page_key)
                except (TypeError, ValueError):
                    page_num = 0
                if not isinstance(items, list):
                    continue
                for item in items:
                    parsed = cls._coerce_result(item, page_num=page_num)
                    if parsed is not None:
                        yield parsed
            return

        if isinstance(ocr_results, list):
            for item in ocr_results:
                parsed = cls._coerce_result(item, page_num=None)
                if parsed is not None:
                    yield parsed

    @staticmethod
    def _coerce_result(item: Any, page_num: Optional[int]) -> Optional[OCRResult]:
        if isinstance(item, OCRResult):
            return item
        if not isinstance(item, dict):
            return None
        try:
            result_page = int(
                item.get("page_num", page_num if page_num is not None else 0)
            )
            x = float(item.get("x", 0.0))
            y = float(item.get("y", 0.0))
            width = float(item.get("width", 0.0))
            height = float(item.get("height", 0.0))
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            return None
        raw_color = item.get("text_color")
        text_color: Optional[List[float]] = None
        if isinstance(raw_color, (list, tuple)) and len(raw_color) >= 3:
            try:
                text_color = [float(raw_color[0]), float(raw_color[1]), float(raw_color[2])]
            except (TypeError, ValueError):
                text_color = None
        raw_opacity = item.get("text_opacity")
        text_opacity: Optional[float] = None
        if raw_opacity is not None:
            try:
                text_opacity = float(raw_opacity)
            except (TypeError, ValueError):
                text_opacity = None
        return OCRResult(
            text=str(item.get("text", "") or ""),
            x=x,
            y=y,
            width=width,
            height=height,
            page_num=result_page,
            confidence=confidence,
            text_color=text_color,
            text_opacity=text_opacity,
        )

    @staticmethod
    def _resolve_target_pages(
        page_count: int,
        page_filter: Optional[Sequence[int]],
    ) -> List[int]:
        if page_filter is None:
            return list(range(page_count))
        pages: List[int] = []
        for value in page_filter:
            try:
                page_num = int(value)
            except (TypeError, ValueError):
                continue
            if page_num < 0 or page_num >= page_count:
                continue
            if page_num not in pages:
                pages.append(page_num)
        return pages
