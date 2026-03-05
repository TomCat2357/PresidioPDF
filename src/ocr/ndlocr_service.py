"""NDLOCR-Liteラッパー。"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import tempfile
from importlib import metadata as importlib_metadata
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import fitz

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """OCRの単語矩形。"""

    text: str
    x: float
    y: float
    width: float
    height: float
    page_num: int
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "page_num": self.page_num,
            "confidence": self.confidence,
        }


class NDLOCRService:
    """NDLOCR-Liteのラッパー。"""

    _DISTRIBUTION_NAME = "ndlocr-lite"
    _DISTRIBUTION_OCR_RELATIVE_PATH = Path("ocr.py")
    _MODULE_CANDIDATES: Tuple[Tuple[str, str, str], ...] = (
        ("ndlocr_lite.ocr", "process", "legacy"),
        ("ndlocr_lite", "process", "legacy"),
        ("ndlocr.ocr", "process", "legacy"),
        ("ndlocr", "process", "legacy"),
        # ndlocr-lite>=1.0.0 はトップレベル `ocr.py` を提供する。
        ("ocr", "process", "args"),
    )

    def __init__(self):
        self._process_callable: Optional[Callable[..., Any]] = None

    @classmethod
    def is_available(cls) -> bool:
        """ndlocr-liteが利用可能か判定する。"""
        # 1. distribution path経由の確認（ファイル存在 + 実際のロード）
        dist_ocr_path = cls._get_distribution_ocr_path()
        if dist_ocr_path and cls._looks_like_ndlocr_ocr_path(dist_ocr_path):
            module = cls._load_module_from_path(
                dist_ocr_path,
                "_presidiopdf_ndlocr_availability_check",
            )
            if module is not None and callable(getattr(module, "process", None)):
                return True

        for module_name, attr_name, mode in cls._MODULE_CANDIDATES:
            try:
                spec = importlib.util.find_spec(module_name)
            except Exception:
                spec = None
            if spec is None:
                continue
            if mode == "args":
                spec_origin = Path(spec.origin) if spec.origin else None
                if spec_origin and spec_origin.exists():
                    base_dir = spec_origin.resolve().parent
                    if (base_dir / "model" / "deim-s-1024x1024.onnx").exists():
                        return True
                continue
            try:
                module = importlib.import_module(module_name)
                candidate = getattr(module, attr_name, None)
            except Exception:
                continue
            if callable(candidate):
                return True
        return False

    def run_ocr_on_page(
        self,
        page_pixmap: fitz.Pixmap,
        existing_text_rects: Optional[Sequence[Sequence[float]]] = None,
        *,
        page_num: int = 0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ) -> List[OCRResult]:
        """1ページ分のOCRを実行して座標付き結果を返す。"""
        if not isinstance(page_pixmap, fitz.Pixmap):
            raise TypeError("page_pixmapはfitz.Pixmapである必要があります")

        image = self._pixmap_to_image(page_pixmap)
        _, image_draw_module = self._get_pillow_modules()
        draw = image_draw_module.Draw(image)
        for rect in existing_text_rects or []:
            normalized = self._normalize_rect(rect)
            if not normalized:
                continue
            draw.rectangle(normalized, fill=(255, 255, 255))

        process_callable = self._get_process_callable()
        with tempfile.TemporaryDirectory(prefix="presidiopdf-ndlocr-") as temp_dir:
            image_path = Path(temp_dir) / "page.png"
            image.save(image_path, format="PNG")
            raw_result = process_callable(str(image_path))

        results: List[OCRResult] = []
        for item in self._iter_result_items(raw_result):
            parsed = self._parse_raw_result_item(item)
            if parsed is None:
                continue
            text, (x, y, w, h), confidence = parsed
            if not text or w <= 0.0 or h <= 0.0:
                continue
            results.append(
                OCRResult(
                    text=text,
                    x=float(x) * float(scale_x),
                    y=float(y) * float(scale_y),
                    width=float(w) * float(scale_x),
                    height=float(h) * float(scale_y),
                    page_num=int(page_num),
                    confidence=float(confidence),
                )
            )

        return results

    def run_ocr_on_pdf(
        self,
        pdf_path: Path,
        page_filter: Optional[Sequence[int]] = None,
        dpi: int = 300,
    ) -> Dict[int, List[OCRResult]]:
        """PDF全体または指定ページでOCRを実行する。"""
        if not isinstance(pdf_path, Path):
            pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")

        try:
            dpi_value = int(dpi)
        except (TypeError, ValueError) as exc:
            raise ValueError("dpiは整数で指定してください") from exc
        if dpi_value <= 0:
            raise ValueError("dpiは1以上で指定してください")

        result: Dict[int, List[OCRResult]] = {}
        with fitz.open(str(pdf_path)) as doc:
            target_pages = self._resolve_target_pages(len(doc), page_filter)
            scale = 72.0 / float(dpi_value)
            for page_num in target_pages:
                page = doc[page_num]
                pixmap = page.get_pixmap(dpi=dpi_value, alpha=False)
                existing_rects = self._extract_existing_text_rects(page, dpi_value)
                result[page_num] = self.run_ocr_on_page(
                    pixmap,
                    existing_rects,
                    page_num=page_num,
                    scale_x=scale,
                    scale_y=scale,
                )
        return result

    def _get_process_callable(self) -> Callable[..., Any]:
        if callable(self._process_callable):
            return self._process_callable

        for module_name, attr_name, mode in self._MODULE_CANDIDATES:
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue
            candidate = getattr(module, attr_name, None)
            if callable(candidate):
                if mode == "args":
                    if not self._looks_like_ndlocr_ocr_module(module):
                        continue
                    self._process_callable = self._build_args_process_runner(
                        module=module,
                        process_callable=candidate,
                    )
                else:
                    self._process_callable = candidate
                return self._process_callable

        dist_ocr_path = self._get_distribution_ocr_path()
        if dist_ocr_path and self._looks_like_ndlocr_ocr_path(dist_ocr_path):
            module = self._load_module_from_path(
                dist_ocr_path,
                "_presidiopdf_ndlocr_distribution_ocr",
            )
            if module is not None:
                candidate = getattr(module, "process", None)
                if callable(candidate):
                    self._process_callable = self._build_args_process_runner(
                        module=module,
                        process_callable=candidate,
                    )
                    return self._process_callable

        raise ImportError(
            "NDLOCR-Liteのprocess()が見つかりません。"
            "`pip install ndlocr-lite` の実行状態と、同名の `ocr.py` 競合を確認してください。"
        )

    @classmethod
    def _get_distribution_ocr_path(cls) -> Optional[Path]:
        try:
            distribution = importlib_metadata.distribution(cls._DISTRIBUTION_NAME)
            ocr_path = Path(
                distribution.locate_file(cls._DISTRIBUTION_OCR_RELATIVE_PATH)
            ).resolve()
        except Exception:
            return None
        if not ocr_path.exists() or not ocr_path.is_file():
            return None
        return ocr_path

    @staticmethod
    def _load_module_from_path(module_path: Path, module_name: str) -> Optional[Any]:
        try:
            spec = importlib.util.spec_from_file_location(
                module_name,
                str(module_path),
            )
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception:
            return None

    @staticmethod
    def _looks_like_ndlocr_ocr_path(module_path: Path) -> bool:
        if not module_path.exists():
            return False
        base_dir = module_path.resolve().parent
        required_files = (
            base_dir / "model" / "deim-s-1024x1024.onnx",
            base_dir / "model" / "parseq-ndl-16x768-100-tiny-165epoch-tegaki2.onnx",
            base_dir / "config" / "ndl.yaml",
            base_dir / "config" / "NDLmoji.yaml",
        )
        return all(path.exists() for path in required_files)

    @staticmethod
    def _looks_like_ndlocr_ocr_module(module: Any) -> bool:
        module_path = Path(getattr(module, "__file__", "") or "")
        return NDLOCRService._looks_like_ndlocr_ocr_path(module_path)

    @staticmethod
    def _build_args_process_runner(
        *,
        module: Any,
        process_callable: Callable[..., Any],
    ) -> Callable[[str], Any]:
        module_path = Path(getattr(module, "__file__", "") or "")
        base_dir = module_path.resolve().parent

        def _runner(image_path: str) -> Any:
            source_image = Path(image_path)
            output_dir = source_image.parent
            args = Namespace(
                sourcedir=None,
                sourceimg=str(source_image),
                output=str(output_dir),
                viz=False,
                det_weights=str(base_dir / "model" / "deim-s-1024x1024.onnx"),
                det_classes=str(base_dir / "config" / "ndl.yaml"),
                det_score_threshold=0.2,
                det_conf_threshold=0.25,
                det_iou_threshold=0.2,
                simple_mode=False,
                rec_weights30=str(
                    base_dir / "model" / "parseq-ndl-16x256-30-tiny-192epoch-tegaki3.onnx"
                ),
                rec_weights50=str(
                    base_dir / "model" / "parseq-ndl-16x384-50-tiny-146epoch-tegaki2.onnx"
                ),
                rec_weights=str(
                    base_dir / "model" / "parseq-ndl-16x768-100-tiny-165epoch-tegaki2.onnx"
                ),
                rec_classes=str(base_dir / "config" / "NDLmoji.yaml"),
                device="cpu",
            )
            process_callable(args)
            output_json = output_dir / f"{source_image.stem}.json"
            if not output_json.exists():
                return []
            try:
                data = json.loads(output_json.read_text(encoding="utf-8"))
            except Exception:
                return []
            if isinstance(data, dict):
                contents = data.get("contents")
                if (
                    isinstance(contents, list)
                    and contents
                    and isinstance(contents[0], list)
                ):
                    return contents[0]
            return data

        return _runner

    @staticmethod
    def _resolve_target_pages(
        page_count: int,
        page_filter: Optional[Sequence[int]],
    ) -> List[int]:
        if page_filter is None:
            return list(range(page_count))
        target_pages: List[int] = []
        for raw_page_num in page_filter:
            try:
                page_num = int(raw_page_num)
            except (TypeError, ValueError):
                continue
            if page_num < 0 or page_num >= page_count:
                continue
            if page_num not in target_pages:
                target_pages.append(page_num)
        return target_pages

    @staticmethod
    def _get_pillow_modules():
        try:
            from PIL import Image, ImageDraw
        except Exception as exc:
            raise ImportError(
                "OCR機能にはPillowが必要です。`pip install pillow` を確認してください。"
            ) from exc
        return Image, ImageDraw

    @staticmethod
    def _pixmap_to_image(pixmap: fitz.Pixmap) -> Any:
        image_module, _ = NDLOCRService._get_pillow_modules()
        mode = "RGBA" if pixmap.alpha else "RGB"
        image = image_module.frombytes(
            mode, (pixmap.width, pixmap.height), pixmap.samples
        )
        if mode == "RGBA":
            image = image.convert("RGB")
        return image

    @staticmethod
    def _extract_existing_text_rects(
        page: fitz.Page,
        dpi: int,
    ) -> List[Tuple[float, float, float, float]]:
        text_dict = page.get_text("dict") or {}
        blocks = text_dict.get("blocks", []) if isinstance(text_dict, dict) else []
        scale = float(dpi) / 72.0
        rects: List[Tuple[float, float, float, float]] = []
        for block in blocks:
            if not isinstance(block, dict) or int(block.get("type", -1)) != 0:
                continue
            for line in block.get("lines", []) or []:
                if not isinstance(line, dict):
                    continue
                for span in line.get("spans", []) or []:
                    if not isinstance(span, dict):
                        continue
                    normalized = NDLOCRService._normalize_rect(span.get("bbox"))
                    if not normalized:
                        continue
                    x0, y0, x1, y1 = normalized
                    rects.append((x0 * scale, y0 * scale, x1 * scale, y1 * scale))
        return rects

    @staticmethod
    def _normalize_rect(raw_rect: Any) -> Optional[Tuple[float, float, float, float]]:
        if isinstance(raw_rect, fitz.Rect):
            x0, y0, x1, y1 = raw_rect
        elif isinstance(raw_rect, dict):
            if {"x", "y", "width", "height"} <= set(raw_rect.keys()):
                try:
                    x0 = float(raw_rect.get("x"))
                    y0 = float(raw_rect.get("y"))
                    x1 = x0 + float(raw_rect.get("width"))
                    y1 = y0 + float(raw_rect.get("height"))
                except (TypeError, ValueError):
                    return None
            elif {"left", "top", "right", "bottom"} <= set(raw_rect.keys()):
                try:
                    x0 = float(raw_rect.get("left"))
                    y0 = float(raw_rect.get("top"))
                    x1 = float(raw_rect.get("right"))
                    y1 = float(raw_rect.get("bottom"))
                except (TypeError, ValueError):
                    return None
            else:
                return None
        elif isinstance(raw_rect, (list, tuple)):
            if raw_rect and all(
                isinstance(point, (list, tuple)) and len(point) >= 2
                for point in raw_rect
            ):
                points: List[Tuple[float, float]] = []
                for point in raw_rect:
                    try:
                        points.append((float(point[0]), float(point[1])))
                    except (TypeError, ValueError):
                        return None
                x0 = min(point[0] for point in points)
                y0 = min(point[1] for point in points)
                x1 = max(point[0] for point in points)
                y1 = max(point[1] for point in points)
            elif len(raw_rect) >= 8:
                try:
                    numbers = [float(value) for value in raw_rect[:8]]
                except (TypeError, ValueError):
                    return None
                points = list(zip(numbers[0::2], numbers[1::2]))
                x0 = min(point[0] for point in points)
                y0 = min(point[1] for point in points)
                x1 = max(point[0] for point in points)
                y1 = max(point[1] for point in points)
            elif len(raw_rect) >= 4:
                try:
                    x0 = float(raw_rect[0])
                    y0 = float(raw_rect[1])
                    x1 = float(raw_rect[2])
                    y1 = float(raw_rect[3])
                except (TypeError, ValueError):
                    return None
            else:
                return None
        else:
            return None

        if x1 <= x0 or y1 <= y0:
            return None
        return x0, y0, x1, y1

    @staticmethod
    def _iter_result_items(raw_result: Any) -> Iterable[Any]:
        if isinstance(raw_result, list):
            return raw_result
        if isinstance(raw_result, tuple):
            return list(raw_result)
        if isinstance(raw_result, dict):
            for key in ("results", "result", "lines", "ocr_results", "items", "data"):
                value = raw_result.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, tuple):
                    return list(value)
            if {"text", "bbox"} <= set(raw_result.keys()) or {"text", "box"} <= set(
                raw_result.keys()
            ):
                return [raw_result]
        return []

    @staticmethod
    def _parse_raw_result_item(
        item: Any,
    ) -> Optional[Tuple[str, Tuple[float, float, float, float], float]]:
        if isinstance(item, dict):
            text = str(item.get("text", "") or "").strip()
            raw_box = item.get("bbox")
            if raw_box is None:
                raw_box = item.get("box")
            if raw_box is None:
                raw_box = item.get("points")
            if raw_box is None:
                raw_box = item.get("polygon")
            if raw_box is None:
                raw_box = item.get("boundingBox")
            confidence = item.get(
                "confidence", item.get("score", item.get("prob", 0.0))
            )
        elif isinstance(item, (list, tuple)):
            if len(item) < 2:
                return None
            text = str(item[0] or "").strip()
            raw_box = item[1]
            confidence = item[2] if len(item) >= 3 else 0.0
        else:
            return None

        normalized = NDLOCRService._normalize_rect(raw_box)
        if not normalized:
            return None
        x0, y0, x1, y1 = normalized

        try:
            score = float(confidence)
        except (TypeError, ValueError):
            score = 0.0

        return text, (x0, y0, x1 - x0, y1 - y0), score
