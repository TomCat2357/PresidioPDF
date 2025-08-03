#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDFからの注釈読み取りと復元
"""
import logging
import json
import fitz  # PyMuPDF
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from config_manager import ConfigManager

logger = logging.getLogger(__name__)


class PDFAnnotator:
    """PDFの注釈読み取りと復元を担当するクラス"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def read_pdf_annotations(self, pdf_path: str) -> List[Dict]:
        """PDFから既存の注釈・ハイライトを読み取る"""
        logger.info(f"PDF注釈読み取り開始: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            all_annotations = []

            for page_num, page in enumerate(doc):
                for annot in page.annots():
                    try:
                        annot_info = self._extract_annotation_info(
                            annot, page_num + 1, page
                        )
                        if annot_info:
                            all_annotations.append(annot_info)
                    except Exception as e:
                        logger.warning(
                            f"注釈読み取りエラー (ページ{page_num + 1}): {e}"
                        )

            doc.close()
            logger.info(f"PDF注釈読み取り完了: {len(all_annotations)}件の注釈を検出")
            return all_annotations

        except Exception as e:
            logger.error(f"PDF注釈読み取りエラー: {e}")
            raise

    def restore_pdf_from_report(self, doc: fitz.Document, report_path: str) -> int:
        """レポートからPDFの注釈・ハイライトを復元"""
        logger.info(f"レポートからPDF復元開始: {doc.name} <- {report_path}")

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report_data = json.load(f)

            annotations = report_data.get("annotations", [])
            if not annotations:
                logger.warning("レポートに注釈データが見つかりません")
                return 0

            restored_count = 0

            for annotation_data in annotations:
                try:
                    if self._restore_single_annotation(doc, annotation_data):
                        restored_count += 1
                except Exception as e:
                    logger.warning(
                        f"注釈復元エラー: {e} (注釈: {annotation_data.get('annotation_type', 'Unknown')})"
                    )

            logger.info(f"PDF復元完了: {restored_count}件の注釈・ハイライトを復元")
            return restored_count

        except FileNotFoundError:
            logger.error(f"レポートファイルが見つかりません: {report_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"レポートファイルの読み込みエラー: {e}")
            raise
        except Exception as e:
            logger.error(f"PDF復元エラー: {e}")
            raise

    def _restore_single_annotation(
        self, doc: fitz.Document, annotation_data: Dict
    ) -> bool:
        """単一の注釈・ハイライトを復元"""
        try:
            page_num = annotation_data.get("coordinates", {}).get("page_number", 1) - 1

            if not (0 <= page_num < len(doc)):
                logger.warning(f"無効なページ番号: {page_num + 1}")
                return False

            page = doc[page_num]
            annotation_type = annotation_data.get("annotation_type", "")
            coordinates = annotation_data.get("coordinates", {})

            if annotation_type == "Highlight":
                return self._restore_highlight_from_data(
                    page, annotation_data, coordinates
                )
            else:
                return self._restore_annotation_from_data(
                    page, annotation_data, coordinates
                )

        except Exception as e:
            logger.error(f"単一注釈復元エラー: {e}")
            return False

    def _extract_annotation_info(self, annot, page_number: int, page) -> Optional[Dict]:
        """注釈から詳細情報を抽出"""
        try:
            rect = annot.rect
            annot_type = annot.type[1]

            coordinates = {
                "page_number": page_number,
                "x0": float(rect.x0),
                "y0": float(rect.y0),
                "x1": float(rect.x1),
                "y1": float(rect.y1),
                "width": float(rect.width),
                "height": float(rect.height),
            }

            covered_text = self._extract_covered_text(rect, page)

            return {
                "annotation_type": annot_type,
                "coordinates": coordinates,
                "covered_text": covered_text,
                "title": annot.info.get("title", ""),
                "content": annot.info.get("content", ""),
                "color_info": self._extract_annotation_colors(annot),
                "opacity": self._extract_annotation_opacity(annot),
                "creation_date": annot.info.get("creationDate", ""),
                "modification_date": annot.info.get("modDate", ""),
                "author": annot.info.get("subject", ""),
            }

        except Exception as e:
            logger.debug(f"注釈情報抽出エラー: {e}")
            return None

    def _extract_covered_text(self, rect: fitz.Rect, page) -> str:
        """注釈がカバーしているテキストを抽出"""
        try:
            text_instances = page.get_text("words", clip=rect)
            if text_instances:
                return " ".join([word[4] for word in text_instances])

            expanded_rect = rect + (-5, -5, 5, 5)
            text_instances = page.get_text("words", clip=expanded_rect)
            return (
                " ".join([word[4] for word in text_instances]) if text_instances else ""
            )

        except Exception as e:
            logger.debug(f"カバーテキスト抽出エラー: {e}")
            return ""

    def _extract_annotation_colors(self, annot) -> Dict:
        """注釈の色情報を抽出"""
        try:
            colors = {}
            if annot.colors.get("stroke"):
                stroke = annot.colors["stroke"]
                colors["stroke_color"] = {
                    "rgb": list(stroke),
                    "hex": self._rgb_to_hex(stroke),
                }
            if annot.colors.get("fill"):
                fill = annot.colors["fill"]
                colors["fill_color"] = {
                    "rgb": list(fill),
                    "hex": self._rgb_to_hex(fill),
                }
            return colors
        except Exception as e:
            logger.debug(f"色情報抽出エラー: {e}")
            return {}

    def _rgb_to_hex(self, rgb: List[float]) -> str:
        """RGB値を16進数色コードに変換"""
        try:
            if len(rgb) >= 3:
                return (
                    f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"
                )
            return "#000000"
        except:
            return "#000000"

    def _extract_annotation_opacity(self, annot) -> float:
        """注釈の透明度を抽出"""
        try:
            return float(getattr(annot, "opacity", 1.0))
        except Exception as e:
            logger.debug(f"透明度抽出エラー: {e}")
            return 1.0

    def _restore_highlight_from_data(
        self, page: fitz.Page, data: Dict, coords: Dict
    ) -> bool:
        """データからハイライトを復元"""
        rect = self._extract_rect_from_coordinates(coords)
        if not rect:
            return False

        highlight = page.add_highlight_annot(rect)
        color = self._extract_color_from_report(
            data.get("color_info", {}), "stroke_color"
        )
        if color:
            highlight.set_colors(stroke=color)
        highlight.set_info(title=data.get("title", ""), content=data.get("content", ""))
        highlight.update()
        return True

    def _restore_annotation_from_data(
        self, page: fitz.Page, data: Dict, coords: Dict
    ) -> bool:
        """データから注釈を復元"""
        rect = self._extract_rect_from_coordinates(coords)
        if not rect:
            return False

        annot_type = data.get("annotation_type", "")
        content = data.get("content", "")

        if "FreeText" in annot_type:
            annot = page.add_freetext_annot(rect, content)
        elif "Square" in annot_type:
            annot = page.add_square_annot(rect)
        else:
            annot = page.add_freetext_annot(rect, content)  # Default

        stroke = self._extract_color_from_report(
            data.get("color_info", {}), "stroke_color"
        )
        fill = self._extract_color_from_report(data.get("color_info", {}), "fill_color")
        annot.set_colors(stroke=stroke, fill=fill)
        annot.set_info(title=data.get("title", ""), content=content)
        annot.set_opacity(data.get("opacity", 1.0))
        annot.update()
        return True

    def _extract_rect_from_coordinates(self, coords: Dict) -> Optional[fitz.Rect]:
        """座標辞書からfitz.Rectオブジェクトを生成"""
        try:
            x0, y0, x1, y1 = (
                float(coords["x0"]),
                float(coords["y0"]),
                float(coords["x1"]),
                float(coords["y1"]),
            )
            if x0 >= x1 or y0 >= y1:
                return None
            return fitz.Rect(x0, y0, x1, y1)
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"座標抽出エラー: {e}")
            return None

    def _extract_color_from_report(
        self, color_info: Dict, color_type: str
    ) -> Optional[List[float]]:
        """レポートの色情報からRGBリストを抽出"""
        try:
            if color_type in color_info:
                rgb = color_info[color_type].get("rgb", [])
                if len(rgb) >= 3:
                    return rgb[:3]
            return None
        except Exception as e:
            logger.debug(f"色情報抽出エラー: {e}")
            return None

    def generate_annotations_report(
        self, annotations: List[Dict], pdf_path: str
    ) -> Optional[str]:
        """読み取った注釈のレポートを生成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"annotations_report_{timestamp}.json"

        output_dir = self.config_manager.get_output_dir()
        if output_dir:
            output_dir_path = Path(output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)
            report_filename = str(output_dir_path / report_filename)

        try:
            report_data = {
                "pdf_file": pdf_path,
                "scan_date": datetime.now().isoformat(),
                "total_annotations": len(annotations),
                "annotations_by_type": {},
                "annotations_by_page": {},
                "annotations": annotations,
            }

            for annot in annotations:
                annot_type = annot["annotation_type"]
                report_data["annotations_by_type"][annot_type] = (
                    report_data["annotations_by_type"].get(annot_type, 0) + 1
                )

                page_num = annot["coordinates"]["page_number"]
                report_data["annotations_by_page"][page_num] = (
                    report_data["annotations_by_page"].get(page_num, 0) + 1
                )

            with open(report_filename, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

            logger.info(f"注釈レポートを生成: {report_filename}")
            return report_filename

        except Exception as e:
            logger.error(f"注釈レポート生成エラー: {e}")
            return None
