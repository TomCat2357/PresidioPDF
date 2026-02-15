#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyMuPDF版 PDF個人情報検出・マスキングプロセッサー
"""

import os
import sys
import logging
import json
import shutil
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import fitz  # PyMuPDF

from core.config_manager import ConfigManager
from analysis.analyzer import Analyzer
from pdf.pdf_locator import PDFTextLocator
from pdf.pdf_masker import PDFMasker
from pdf.pdf_annotator import PDFAnnotator

logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDFのPII処理ワークフローを管理するクラス"""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Args:
            config_manager: 設定管理インスタンス
        """
        self.config_manager = config_manager or ConfigManager()
        self._setup_logging()

        self.analyzer = Analyzer(self.config_manager)
        self.masker = PDFMasker(self.config_manager)
        self.annotator = PDFAnnotator(self.config_manager)

        self.processing_stats = {
            "files_processed": 0,
            "files_failed": 0,
            "total_entities_found": 0,
            "entities_by_type": {},
            "start_time": datetime.now().isoformat(),
        }

    def _setup_logging(self):
        """ログ設定を初期化"""
        log_config = self.config_manager.get_logging_config()
        level = getattr(logging, log_config["level"].upper(), logging.INFO)
        logging.getLogger().setLevel(level)

        if log_config.get("log_to_file", False):
            handler = logging.FileHandler(log_config["log_file_path"], encoding="utf-8")
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            logging.getLogger().addHandler(handler)
            logger.info(f"ログファイルに出力: {log_config['log_file_path']}")

    def analyze_pdf(self, pdf_path: str) -> List[Dict]:
        """PDFの個人情報を解析"""
        logger.info(f"PDF解析開始: {pdf_path}")

        doc = fitz.open(pdf_path)
        locator = PDFTextLocator(doc)

        # 改行なしテキストで解析して改行を跨ぐ単語も検出
        full_text_no_newlines = locator.full_text_no_newlines

        enabled_entities = self.config_manager.get_enabled_entities()
        results = self.analyzer.analyze_text(full_text_no_newlines, enabled_entities)

        for result in results:
            start, end = result["start"], result["end"]
            precise_rects_with_pages = locator.locate_pii_by_offset_no_newlines(
                start, end
            )

            # エンティティ情報を更新（ページ番号はPDFTextLocatorから直接取得）
            result["line_rects"] = []
            for rect_data in precise_rects_with_pages:
                result["line_rects"].append(
                    {"rect": rect_data["rect"], "page_num": rect_data["page_num"]}
                )

            if result["line_rects"]:
                first_rect_info = result["line_rects"][0]
                main_rect = first_rect_info["rect"]
                page_num = first_rect_info["page_num"]
                result["coordinates"] = {
                    "page_number": page_num + 1,
                    "x0": float(main_rect.x0),
                    "y0": float(main_rect.y0),
                    "x1": float(main_rect.x1),
                    "y1": float(main_rect.y1),
                }
                result["page_info"] = {"page_number": page_num + 1}
            else:
                result["coordinates"] = {}
                result["page_info"] = {}

        doc.close()

        logger.info(f"PDF解析完了: {len(results)}件の個人情報を検出")
        return sorted(
            results,
            key=lambda x: (
                x.get("page_info", {}).get("page_number", 0),
                x.get("coordinates", {}).get("y0", 0),
            ),
        )

    def process_pdf_file(self, input_path: str, masking_method: str = None, embed_coordinates: bool = False) -> Dict:
        """単一PDFファイルを処理"""
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"ファイルが見つかりません: {input_path}")

        if self._should_skip_file(input_path):
            logger.info(f"ファイルをスキップ: {input_path}")
            return {
                "input_file": input_path,
                "skipped": True,
                "reason": "除外パターンにマッチ",
            }

        logger.info(f"PDF処理開始: {input_path}")
        backup_path = self._create_backup(input_path)

        try:
            entities = self.analyze_pdf(input_path)
            output_path = self.masker.apply_masking(
                input_path, entities, masking_method
            )
            
            # 座標マップ埋め込み処理
            if embed_coordinates:
                self._embed_coordinate_map(input_path, output_path)
            
            logger.info(
                f"PDF処理完了: {output_path} ({len(entities)}件の個人情報を処理)"
            )

            summary = self._create_summary(
                input_path, output_path, backup_path, entities
            )
            self._update_stats(summary)
            return summary

        except Exception as e:
            logger.error(f"PDF処理エラー: {e}")
            self.processing_stats["files_failed"] += 1
            raise

    def process_files(self, path: str, masking_method: str = None, embed_coordinates: bool = False) -> List[Dict]:
        """ファイルまたはフォルダを処理"""
        if self.config_manager.is_read_mode_enabled():
            return self._process_files_read_mode(path)

        files_to_process = self._get_files_from_path(path)
        results = []
        for file_path in files_to_process:
            try:
                result = self.process_pdf_file(file_path, masking_method, embed_coordinates)
                results.append(result)
            except Exception as e:
                logger.error(f"ファイル処理エラー ({file_path}): {e}")
                results.append({"input_file": file_path, "error": str(e)})

        self._generate_report(results)
        return results

    def _process_files_read_mode(self, path: str) -> List[Dict]:
        """読み取りモードでファイルを処理"""
        files_to_read = self._get_files_from_path(path)
        results = []
        for file_path in files_to_read:
            try:
                result = self._read_pdf_file(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"ファイル読み取りエラー ({file_path}): {e}")
                results.append({"input_file": file_path, "error": str(e)})
        return results

    def _read_pdf_file(self, pdf_path: str) -> Dict:
        """単一PDFファイルから注釈を読み取り"""
        if self._should_skip_file(pdf_path):
            return {
                "input_file": pdf_path,
                "skipped": True,
                "reason": "除外パターンにマッチ",
            }

        logger.info(f"PDF注釈読み取り開始: {pdf_path}")
        try:
            annotations = self.annotator.read_pdf_annotations(pdf_path)
            report_file = None
            if self.config_manager.should_generate_read_report():
                report_file = self.annotator.generate_annotations_report(
                    annotations, pdf_path
                )

            logger.info(f"PDF注釈読み取り完了: {pdf_path} ({len(annotations)}件の注釈)")
            return {
                "input_file": pdf_path,
                "total_annotations": len(annotations),
                "annotations": annotations,
                "report_file": report_file,
            }
        except Exception as e:
            logger.error(f"PDF読み取りエラー: {e}")
            raise

    def _get_files_from_path(self, path: str) -> List[str]:
        """指定されたパスから処理対象のPDFファイルリストを取得"""
        if os.path.isfile(path):
            return [path] if path.lower().endswith(".pdf") else []
        elif os.path.isdir(path):
            import glob

            if self.config_manager.should_search_recursively():
                return glob.glob(os.path.join(path, "**", "*.pdf"), recursive=True)
            else:
                return glob.glob(os.path.join(path, "*.pdf"))
        return []

    def _create_summary(self, in_path, out_path, back_path, entities) -> Dict:
        """処理結果のサマリーを生成"""
        summary = {
            "input_file": in_path,
            "output_file": out_path,
            "backup_file": back_path,
            "total_entities_found": len(entities),
            "entities_by_type": {},
        }

        # 詳細なエンティティ情報を含める場合
        if self.config_manager.should_include_detected_text_in_pdf_report():
            summary["detected_entities"] = []
            for entity in entities:
                entity_detail = {
                    "entity_type": entity["entity_type"],
                    "text": entity["text"],
                    "coordinates": entity.get("coordinates", {}),
                    "page_number": entity.get("page_info", {}).get("page_number", 1),
                }
                summary["detected_entities"].append(entity_detail)

        for entity in entities:
            e_type = entity["entity_type"]
            summary["entities_by_type"][e_type] = (
                summary["entities_by_type"].get(e_type, 0) + 1
            )
        return summary

    def _update_stats(self, summary: Dict):
        """統計情報を更新"""
        self.processing_stats["files_processed"] += 1
        self.processing_stats["total_entities_found"] += summary["total_entities_found"]
        for e_type, count in summary["entities_by_type"].items():
            self.processing_stats["entities_by_type"][e_type] = (
                self.processing_stats["entities_by_type"].get(e_type, 0) + count
            )

    def _generate_report(self, results: List[Dict]):
        """処理結果のレポートを生成"""
        if not self.config_manager.should_generate_pdf_report():
            return None

        fmt = self.config_manager.get_pdf_report_format()
        prefix = self.config_manager.get_pdf_report_prefix()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"{prefix}_{timestamp}.{fmt}"

        output_dir = self.config_manager.get_output_dir()
        if output_dir:
            report_filename = str(Path(output_dir) / report_filename)

        try:
            if fmt == "json":
                report_data = {
                    "processing_stats": self.processing_stats,
                    "file_results": results,
                }
                with open(report_filename, "w", encoding="utf-8") as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
            elif fmt == "csv":
                import csv

                with open(report_filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        ["File", "Entities Found", "Status", "Entity Types"]
                    )
                    for res in results:
                        if "error" not in res and "skipped" not in res:
                            types = ", ".join(
                                f"{k}:{v}"
                                for k, v in res.get("entities_by_type", {}).items()
                            )
                            writer.writerow(
                                [
                                    res["input_file"],
                                    res["total_entities_found"],
                                    "Success",
                                    types,
                                ]
                            )
                        else:
                            status = "Error" if "error" in res else "Skipped"
                            writer.writerow([res["input_file"], 0, status, ""])

            logger.info(f"レポートを生成: {report_filename}")
        except Exception as e:
            logger.error(f"レポート生成でエラー: {e}")

    def _embed_coordinate_map(self, original_pdf_path: str, output_pdf_path: str) -> bool:
        """座標マップを出力PDFに埋め込む（cli.common.embed_coordinate_map に委譲）"""
        try:
            from src.cli.common import embed_coordinate_map
            return embed_coordinate_map(original_pdf_path, output_pdf_path)
        except ImportError:
            # src. プレフィックスなしの実行環境フォールバック
            from cli.common import embed_coordinate_map  # type: ignore[import-not-found]
            return embed_coordinate_map(original_pdf_path, output_pdf_path)

    def _create_backup(self, file_path: str) -> Optional[str]:
        """ファイルのバックアップ出力は廃止（常にNone）"""
        return None

    def _should_skip_file(self, file_path: str) -> bool:
        """ファイルをスキップすべきか判定"""
        patterns = self.config_manager.get_pdf_file_exclusions()
        file_name = os.path.basename(file_path)
        for pattern in patterns:
            if fnmatch.fnmatch(file_name, pattern):
                logger.debug(f"ファイル除外パターンにマッチ: {file_path}")
                return True
        return False
