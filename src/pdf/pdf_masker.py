#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDFへのマスキング（注釈・ハイライト）適用
"""
import logging
import shutil
import fitz  # PyMuPDF
from typing import List, Dict, Optional
from pathlib import Path

from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class PDFMasker:
    """PDFへのマスキング処理を担当するクラス"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def apply_masking(
        self, pdf_path: str, entities: List[Dict], masking_method: str = None
    ) -> str:
        """PyMuPDFを使用してPDFにマスキングを適用"""
        if masking_method is None:
            masking_method = self.config_manager.get_pdf_masking_method()

        output_path = self._generate_output_path(pdf_path)

        try:
            operation_mode = self.config_manager.get_operation_mode()

            shutil.copy2(pdf_path, output_path)

            if masking_method == "annotation":
                return self._apply_annotation_masking_with_mode(
                    output_path, entities, operation_mode
                )
            elif masking_method == "highlight":
                return self._apply_highlight_masking_with_mode(
                    output_path, entities, operation_mode
                )
            elif masking_method == "both":
                self._apply_highlight_masking_with_mode(
                    output_path, entities, operation_mode
                )
                return self._apply_annotation_masking_with_mode(
                    output_path, entities, "append"
                )
            else:
                raise ValueError(f"未対応のマスキング方式: {masking_method}")

        except Exception as e:
            logger.error(f"マスキング適用エラー: {e}")
            shutil.copy2(pdf_path, output_path)
            logger.warning(
                "マスキング処理に失敗しました。元のファイルをコピーしました。"
            )
            return output_path

    def _generate_output_path(self, input_path: str) -> str:
        """出力ファイルパスを生成"""
        suffix = self.config_manager.get_pdf_output_suffix()
        path_obj = Path(input_path)

        output_dir = self.config_manager.get_output_dir()
        if output_dir:
            output_dir_path = Path(output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)
            return str(output_dir_path / f"{path_obj.stem}{suffix}{path_obj.suffix}")
        else:
            return str(path_obj.parent / f"{path_obj.stem}{suffix}{path_obj.suffix}")

    def _apply_annotation_masking_with_mode(
        self, pdf_path: str, entities: List[Dict], operation_mode: str
    ) -> str:
        """操作モードに対応した注釈マスキング"""
        logger.info(f"注釈マスキング適用中: {pdf_path} (モード: {operation_mode})")

        try:
            doc = fitz.open(pdf_path)

            if operation_mode == "clear_all":
                self._clear_all_annotations(doc)
                logger.info("既存の全注釈を削除しました")
            elif operation_mode == "reset_and_append":
                self._clear_all_annotations(doc)
                logger.info("既存の全注釈を削除しました（リセット後追加モード）")

            existing_annotations = []
            if self.config_manager.should_remove_identical_annotations():
                existing_annotations = self._get_existing_annotations(doc)

            annotations_added = 0

            for entity in entities:
                # 複数行に対応するため、line_rectsを優先的に使用
                rects_to_annotate = entity.get("line_rects", [])
                if not rects_to_annotate:
                    # line_rectsがない場合は従来のcoordinatesを使用
                    coords = entity.get("coordinates", {})
                    page_num = coords.get("page_number", 1) - 1
                    if page_num >= len(doc):
                        continue

                    x0, y0, x1, y1 = (
                        float(coords.get("x0", 0)),
                        float(coords.get("y0", 0)),
                        float(coords.get("x1", 0)),
                        float(coords.get("y1", 0)),
                    )
                    if x0 >= x1 or y0 >= y1:
                        continue
                    rect = fitz.Rect(x0, y0, x1, y1)
                    if rect.is_empty or rect.is_infinite:
                        continue
                    rects_to_annotate = [{"rect": rect, "page_num": page_num}]

                for rect_info in rects_to_annotate:
                    rect = rect_info.get("rect")
                    page_num = rect_info.get("page_num")
                    if not isinstance(
                        rect, fitz.Rect
                    ):  # 辞書からRectオブジェクトへ変換
                        rect = fitz.Rect(rect["x0"], rect["y0"], rect["x1"], rect["y1"])

                    if self._is_duplicate_annotation(
                        rect, entity, existing_annotations, page_num
                    ):
                        logger.debug(
                            f"重複注釈をスキップ: {entity['text']} ({entity['entity_type']})"
                        )
                        continue

                    page = doc[page_num]
                    self._add_single_annotation(page, rect, entity)
                    annotations_added += 1

            doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            doc.close()

            logger.info(
                f"注釈マスキング完了: {pdf_path} ({annotations_added}件の注釈を追加)"
            )
            return pdf_path

        except Exception as e:
            logger.error(f"注釈マスキングエラー: {e}")
            raise

    def _apply_highlight_masking_with_mode(
        self, pdf_path: str, entities: List[Dict], operation_mode: str
    ) -> str:
        """操作モードに対応したハイライトマスキング"""
        logger.info(
            f"ハイライトマスキング適用中: {pdf_path} (モード: {operation_mode})"
        )

        try:
            doc = fitz.open(pdf_path)

            if operation_mode == "clear_all":
                self._clear_all_highlights(doc)
                logger.info("既存の全ハイライトを削除しました")
            elif operation_mode == "reset_and_append":
                self._clear_all_highlights(doc)
                logger.info("既存の全ハイライトを削除しました（リセット後追加モード）")

            existing_highlights = []
            if self.config_manager.should_remove_identical_annotations():
                existing_highlights = self._get_existing_highlights(doc)

            highlights_added = 0

            for entity in entities:
                rects_to_highlight = entity.get("line_rects", [])
                if not rects_to_highlight:
                    coords = entity.get("coordinates", {})
                    page_num = coords.get("page_number", 1) - 1
                    if page_num >= len(doc):
                        continue

                    x0, y0, x1, y1 = (
                        float(coords.get("x0", 0)),
                        float(coords.get("y0", 0)),
                        float(coords.get("x1", 0)),
                        float(coords.get("y1", 0)),
                    )
                    if x0 >= x1 or y0 >= y1:
                        continue
                    rect = fitz.Rect(x0, y0, x1, y1)
                    if rect.is_empty or rect.is_infinite:
                        continue
                    rects_to_highlight = [{"rect": rect, "page_num": page_num}]

                for rect_info in rects_to_highlight:
                    page_num = int(rect_info.get("page_num"))
                    page = doc[page_num]
                    space = rect_info.get("coord_space") or rect_info.get("space") or "fitz"
                    rdict = rect_info.get("rect") or {}
                    try:
                        x0 = float(rdict["x0"]); y0 = float(rdict["y0"])
                        x1 = float(rdict["x1"]); y1 = float(rdict["y1"])
                    except Exception:
                        continue  # 値が欠けている / 数値化できない
                    r = fitz.Rect(x0, y0, x1, y1)
                    if space == "pdf":
                        ph = page.rect.height
                        r = fitz.Rect(r.x0, ph - r.y1, r.x1, ph - r.y0)  # Y反転
                    r = r & page.rect
                    if (not r) or r.width <= 0 or r.height <= 0:
                        continue
                    # 既存重複チェック
                    if self._is_duplicate_highlight(r, entity, existing_highlights, page_num):
                        continue
                    # 単一Rectごとにハイライト（複数行は複数アノテーションでカバー）
                    self._add_single_highlight(page, r, entity)
                    highlights_added += 1

            doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            doc.close()

            logger.info(
                f"ハイライトマスキング完了: {pdf_path} ({highlights_added}件のハイライトを追加)"
            )
            return pdf_path

        except Exception as e:
            logger.error(f"ハイライトマスキングエラー: {e}")
            raise

    def _add_single_annotation(self, page: fitz.Page, rect: fitz.Rect, entity: Dict):
        """単一の注釈を追加"""
        try:
            color = self._get_annotation_color_pymupdf(entity["entity_type"])
            content = self._generate_annotation_content(entity)
            text_display_mode = self.config_manager.get_masking_text_display_mode()

            if text_display_mode == "silent":
                annot = page.add_square_annot(rect)
                annot.set_colors(stroke=color, fill=[c * 0.3 for c in color])
                annot.set_info(title="", content="")
            else:
                annot = page.add_freetext_annot(
                    rect,
                    content,
                    fontsize=8,
                    text_color=color,
                    fill_color=[c * 0.3 for c in color],
                )
                title = "個人情報検出" if text_display_mode == "verbose" else ""
                annot.set_info(title=title, content=content)

            annot.update()
            logger.debug(f"注釈を追加: {entity['entity_type']} - {entity['text']}")

        except Exception as e:
            logger.warning(f"注釈追加でエラー: {e} (エンティティ: {entity['text']})")

    def _add_single_highlight(self, page: fitz.Page, rect_or_quads, entity: Dict):
        """単一のハイライトを追加（Rect または list[Quad]）"""
        try:
            color = self._get_highlight_color_pymupdf(entity["entity_type"])
            # 形は Rect または list[Quad] のどちらかに限定
            if isinstance(rect_or_quads, list):
                quads = [q for q in rect_or_quads if isinstance(q, fitz.Quad)]
                if not quads:
                    return
                highlight = page.add_highlight_annot(quads)
            else:
                highlight = page.add_highlight_annot(rect_or_quads)
            highlight.set_colors(stroke=color)
            highlight.set_opacity(0.4)
            
            # Creator情報と検出データを埋め込み
            detect_word = str(entity.get("text", ""))
            entity_type = str(entity.get("entity_type", "PII"))
            content_text = f'detect_word:"{detect_word}",entity_type:"{entity_type}"'
            
            highlight.set_info(
                title=entity_type,
                content=content_text
            )
            
            # Creator情報を設定（name フィールドを使用）
            try:
                if hasattr(highlight, 'set_name'):
                    highlight.set_name("origin")
                else:
                    # 直接info辞書を更新
                    highlight.info['name'] = "origin"
            except Exception as e:
                logger.debug(f"Creator設定エラー: {e}")
            
            # 一部のPyMuPDFバージョンではPDF_ANNOT_FLAG_PRINTが存在しない
            flag_const = getattr(fitz, "PDF_ANNOT_FLAG_PRINT", None)
            try:
                if flag_const is not None:
                    # flags属性またはset_flagsメソッドのどちらかに対応
                    if hasattr(highlight, "flags"):
                        highlight.flags |= flag_const
                    elif hasattr(highlight, "set_flags"):
                        highlight.set_flags(flag_const)
                # フラグ設定の可否に関わらず更新を試みる
                highlight.update()
            except Exception:
                # フラグ設定やupdate失敗は致命的ではないため継続
                pass
        except Exception as e:
            logger.warning(f"add_highlight failed: {type(e).__name__}: {e}")

    def _get_annotation_color_pymupdf(self, entity_type: str) -> List[float]:
        """エンティティタイプに応じたPyMuPDF用注釈色を取得"""
        color_mapping = {
            "PERSON": [1.0, 0.0, 0.0],
            "LOCATION": [0.0, 1.0, 0.0],
            "DATE_TIME": [0.0, 0.0, 1.0],
            "PHONE_NUMBER": [1.0, 1.0, 0.0],
            "INDIVIDUAL_NUMBER": [1.0, 0.0, 1.0],
            "YEAR": [0.5, 0.0, 1.0],
            "PROPER_NOUN": [1.0, 0.5, 0.0],
        }
        return color_mapping.get(entity_type, [0.0, 0.0, 0.0])

    def _get_highlight_color_pymupdf(self, entity_type: str) -> List[float]:
        """エンティティタイプに応じたPyMuPDF用ハイライト色を取得"""
        color_mapping = {
            "PERSON": [1.0, 0.8, 0.8],
            "LOCATION": [0.8, 1.0, 0.8],
            "DATE_TIME": [0.8, 0.8, 1.0],
            "PHONE_NUMBER": [1.0, 1.0, 0.8],
            "INDIVIDUAL_NUMBER": [1.0, 0.8, 1.0],
            "YEAR": [0.9, 0.8, 1.0],
            "PROPER_NOUN": [1.0, 0.9, 0.8],
        }
        return color_mapping.get(entity_type, [0.9, 0.9, 0.9])

    def _generate_annotation_content(self, entity: Dict) -> str:
        """注釈内容を生成"""
        text_display_mode = self.config_manager.get_masking_text_display_mode()

        if text_display_mode == "silent":
            return ""

        entity_type = entity["entity_type"]
        text = entity.get("text", "")

        type_names = {
            "PERSON": "人名",
            "LOCATION": "場所",
            "DATE_TIME": "日時",
            "PHONE_NUMBER": "電話番号",
            "INDIVIDUAL_NUMBER": "マイナンバー",
            "YEAR": "年号",
            "PROPER_NOUN": "固有名詞",
        }
        type_name = type_names.get(entity_type, entity_type)

        if text_display_mode == "minimal":
            return type_name
        elif text_display_mode == "verbose":
            content = f"【個人情報】{type_name}"
            annotation_settings = self.config_manager.get_pdf_annotation_settings()
            if annotation_settings.get("include_text", False):
                content += f"\nテキスト: {text[:20]}..."
            return content
        else:
            logger.warning(
                f"未知の文字表示モード: {text_display_mode}. verboseとして扱います。"
            )
            return f"【個人情報】{type_name}"

    def _clear_all_annotations(self, doc):
        """PDFから全ての注釈を削除（ハイライト以外）"""
        try:
            for page in doc:
                for annot in list(page.annots()):
                    if annot.type[1] != "Highlight":
                        page.delete_annot(annot)
        except Exception as e:
            logger.error(f"注釈削除エラー: {e}")

    def _clear_all_highlights(self, doc):
        """PDFから全てのハイライトを削除"""
        try:
            for page in doc:
                for annot in list(page.annots()):
                    if annot.type[1] == "Highlight":
                        page.delete_annot(annot)
        except Exception as e:
            logger.error(f"ハイライト削除エラー: {e}")

    def _get_existing_annotations(self, doc) -> List[Dict]:
        """既存の注釈情報を取得"""
        existing = []
        try:
            for page_num, page in enumerate(doc):
                for annot in page.annots():
                    if annot.type[1] != "Highlight":
                        existing.append(
                            {
                                "rect": annot.rect,
                                "page_num": page_num,
                                "content": annot.info.get("content", ""),
                                "title": annot.info.get("title", ""),
                            }
                        )
        except Exception as e:
            logger.debug(f"既存注釈取得エラー: {e}")
        return existing

    def _get_existing_highlights(self, doc) -> List[Dict]:
        """既存のハイライト情報を取得"""
        existing = []
        try:
            for page_num, page in enumerate(doc):
                for annot in page.annots():
                    if annot.type[1] == "Highlight":
                        # Creator情報を取得
                        creator = getattr(annot, 'name', None) or getattr(annot.info, 'name', None) or ""
                        
                        # Content情報を取得してパース
                        content = annot.info.get("content", "")
                        parsed_data = self._parse_highlight_content(content)
                        
                        highlight_info = {
                            "rect": annot.rect,
                            "page_num": page_num,
                            "content": content,
                            "title": annot.info.get("title", ""),
                            "creator": creator,
                        }
                        
                        # パース済みデータがあれば追加
                        if parsed_data:
                            highlight_info.update(parsed_data)
                            
                        existing.append(highlight_info)
        except Exception as e:
            logger.debug(f"既存ハイライト取得エラー: {e}")
        return existing

    def _parse_highlight_content(self, content: str) -> Dict:
        """ハイライトのcontent文字列をパースして構造化データを取得"""
        result = {}
        try:
            # detect_word:"value",entity_type:"TYPE" 形式のパース
            import re
            
            # detect_word:"..." の抽出
            detect_word_match = re.search(r'detect_word:"([^"]*)"', content)
            if detect_word_match:
                result["detect_word"] = detect_word_match.group(1)
            
            # entity_type:"..." の抽出
            entity_type_match = re.search(r'entity_type:"([^"]*)"', content)
            if entity_type_match:
                result["entity_type"] = entity_type_match.group(1)
                
        except Exception as e:
            logger.debug(f"ハイライトコンテンツパースエラー: {e}")
        
        return result

    def _is_duplicate_annotation(
        self,
        rect: fitz.Rect,
        entity: Dict,
        existing_annotations: List[Dict],
        page_num: int,
    ) -> bool:
        """注釈が重複しているかをチェック"""
        if not self.config_manager.should_remove_identical_annotations():
            return False

        tolerance = self.config_manager.get_annotation_comparison_tolerance()
        entity_text = entity.get("text", "")
        entity_type = entity.get("entity_type", "")

        for existing in existing_annotations:
            if existing["page_num"] != page_num:
                continue

            existing_rect = existing["rect"]

            if (
                abs(rect.x0 - existing_rect.x0) <= tolerance
                and abs(rect.y0 - existing_rect.y0) <= tolerance
                and abs(rect.x1 - existing_rect.x1) <= tolerance
                and abs(rect.y1 - existing_rect.y1) <= tolerance
            ):

                if (
                    existing.get("text", "") == entity_text
                    and existing.get("entity_type", "") == entity_type
                ):
                    return True

        return False

    def _is_duplicate_highlight(
        self,
        rect: fitz.Rect,
        entity: Dict,
        existing_highlights: List[Dict],
        page_num: int,
    ) -> bool:
        """ハイライトが重複しているかをチェック"""
        if not self.config_manager.should_remove_identical_annotations():
            return False

        tolerance = self.config_manager.get_annotation_comparison_tolerance()
        entity_text = entity.get("text", "")

        for existing in existing_highlights:
            if existing["page_num"] != page_num:
                continue

            existing_rect = existing["rect"]

            if (
                abs(rect.x0 - existing_rect.x0) <= tolerance
                and abs(rect.y0 - existing_rect.y0) <= tolerance
                and abs(rect.x1 - existing_rect.x1) <= tolerance
                and abs(rect.y1 - existing_rect.y1) <= tolerance
            ):

                if existing.get("text", "") == entity_text:
                    return True

        return False
