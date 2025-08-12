#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - Webアプリケーションコア処理
"""

import os
import json
import uuid
import logging
import math
import traceback
import shutil
from datetime import datetime
from typing import List, Dict, Optional
import fitz  # PyMuPDF

# 自プロジェクトのモジュールをインポート
from core.config_manager import ConfigManager
from pdf.pdf_processor import PDFProcessor

PRESIDIO_AVAILABLE = True

# ログ設定の初期化（既存のロガーを使用）
logger = logging.getLogger(__name__)


class PresidioPDFWebApp:
    """PDF個人情報マスキングWebアプリケーション"""

    def __init__(self, session_id: str, use_gpu: bool = False):
        self.session_id = session_id
        self.use_gpu = use_gpu
        self.current_pdf_path: Optional[str] = None
        self.detection_results: List[Dict] = []
        self.pdf_document = None
        self.total_pages = 0
        self.settings = {
            "entities": [
                "PERSON",
                "LOCATION",
                "DATE_TIME",
                "PHONE_NUMBER",
                "INDIVIDUAL_NUMBER",
                "YEAR",
                "PROPER_NOUN",
            ],
            "masking_method": "highlight",  # ハイライトのみ（FreeTextは作らない）
            "masking_text_mode": "verbose",
            "spacy_model": "ja_core_news_sm",  # CPUモードデフォルトをsmに変更
            # 重複除去設定（CLI版と同様）
            "deduplication_enabled": False,
            "deduplication_method": "overlap",  # exact, contain, overlap
            "deduplication_priority": "wider_range",  # wider_range, narrower_range, entity_type
            "deduplication_overlap_mode": "partial_overlap",  # contain_only, partial_overlap
        }

        # Presidio プロセッサーの初期化
        self.processor = None
        if PRESIDIO_AVAILABLE:
            try:
                # デフォルトの設定ファイルパスを解決
                config_path = os.path.join(os.getcwd(), "config/config.yaml")

                if os.path.exists(config_path):
                    config_manager = ConfigManager(config_file=config_path)
                    logger.info(f"設定ファイルを使用して初期化: {config_path}")
                else:
                    config_manager = ConfigManager()
                    logger.warning(
                        f"設定ファイルが見つかりません: {config_path}。デフォルト設定で初期化します。"
                    )

                # CPU/GPUモードの設定
                if not self.use_gpu:
                    # CPU強制時の確実な上書き処理
                    config_manager.spacy_model = "ja_core_news_sm"
                    logger.info(
                        f"CPUモードで初期化中: spaCyモデル = {config_manager.spacy_model}"
                    )

                self.processor = PDFProcessor(config_manager)

                mode_str = "GPU" if self.use_gpu else "CPU"
                logger.info(f"Presidio processor初期化完了 ({mode_str}モード)")
            except Exception as e:
                logger.error(f"Presidio processor初期化エラー: {e}")
                self.processor = None

        logger.info(
            f"セッション {session_id} 初期化完了 ({'GPU' if self.use_gpu else 'CPU'}モード)"
        )

    def _reinitialize_processor_with_model(self, spacy_model: str):
        """指定されたspaCyモデルでプロセッサを再初期化"""
        try:
            logger.info(f"プロセッサを再初期化: {spacy_model}")

            # 既存のプロセッサを破棄
            if self.processor:
                self.processor = None

            # 新しい設定でプロセッサを初期化
            config_path = os.path.join(os.getcwd(), "config/config.yaml")

            if os.path.exists(config_path):
                config_manager = ConfigManager(config_file=config_path)
            else:
                config_manager = ConfigManager()

            # spaCyモデルを強制設定
            config_manager.set_spacy_model(spacy_model)

            # CPUモード設定
            if not self.use_gpu:
                logger.info(f"CPUモードで再初期化: spaCyモデル = {spacy_model}")

            self.processor = PDFProcessor(config_manager)

            mode_str = "GPU" if self.use_gpu else "CPU"
            logger.info(f"プロセッサ再初期化完了: {spacy_model} ({mode_str}モード)")

        except Exception as e:
            logger.error(f"プロセッサ再初期化エラー: {e}")
            # エラーが発生した場合はデフォルトに戻す
            try:
                config_manager = ConfigManager()
                config_manager.set_spacy_model("ja_core_news_sm")
                self.processor = PDFProcessor(config_manager)
                logger.warning("デフォルトモデル (ja_core_news_sm) で復旧しました")
            except Exception as fallback_error:
                logger.error(f"フォールバック初期化も失敗: {fallback_error}")
                self.processor = None

    def load_pdf_file(self, file_path: str) -> Dict:
        """PDFファイルを読み込み"""
        try:
            logger.info(f"PDFファイル読み込み開始: {file_path}")
            self.current_pdf_path = file_path
            self.detection_results = []

            if self.pdf_document:
                self.pdf_document.close()

            self.pdf_document = fitz.open(file_path)
            self.total_pages = len(self.pdf_document)

            logger.info(f"PDFファイル読み込み完了: {self.total_pages}ページ")

            return {
                "success": True,
                "message": f"PDFファイル読み込み完了: {os.path.basename(file_path)} ({self.total_pages}ページ)",
                "total_pages": self.total_pages,
                "filename": os.path.basename(file_path),
            }

        except Exception as ex:
            logger.error(f"PDFファイル読み込みエラー: {ex}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"PDFファイルの読み込みに失敗: {str(ex)}",
            }

    def run_detection(self) -> Dict:
        """個人情報検出処理を実行（オフセットベース座標特定）"""
        try:
            # Webの除外パターン(空白区切り, 正規表現)をConfigManagerに反映
            import re
            cm = self.processor.config_manager
            web_patterns = self.settings.get("exclude_regex", [])
            # 互換: 旧キー exclude_words が来たら空白分割して利用
            if not web_patterns:
                legacy = self.settings.get("exclude_words", [])
                if isinstance(legacy, list):
                    legacy = " ".join([s for s in legacy if isinstance(s, str)])
                web_patterns = [p for p in re.split(r"[ \u3000]+", legacy or "") if p]
            ex = cm.get_exclusions()
            ex["text_exclusions_regex"] = web_patterns
            cm.config["exclusions"] = ex

            # Webの追加パターンを共通ロジック（Analyzer）へ委譲するため custom_recognizers に反映
            try:
                add = self.settings.get("additional_words", {}) or {}
                cr = cm.config.get("custom_recognizers", {}) or {}
                # 既存のweb_定義を削除して再構築
                cr = {k: v for k, v in cr.items() if not str(k).startswith("web_")}
                for etype, patterns in add.items():
                    if not isinstance(patterns, list):
                        continue
                    conf = {
                        "enabled": True,
                        "entity_type": etype,
                        "patterns": [
                            {"name": f"web_{etype}_{i}", "regex": p, "score": 1.0}
                            for i, p in enumerate(patterns)
                            if isinstance(p, str) and p
                        ],
                    }
                    cr[f"web_{etype}"] = conf
                cm.config["custom_recognizers"] = cr
            except Exception as e:
                logger.warning(f"web追加パターンの適用に失敗: {e}")
            
            logger.info(f"=== run_detection開始 ===")
            logger.info(f"PDF path: {self.current_pdf_path}")
            logger.info(f"Processor存在: {self.processor is not None}")
            logger.info(f"PRESIDIO_AVAILABLE: {PRESIDIO_AVAILABLE}")

            if not self.processor or not PRESIDIO_AVAILABLE:
                logger.error("Presidio processorが利用できません。")
                return {
                    "success": False,
                    "message": "サーバーエラー: 検出エンジンが利用できません。",
                }

            # 手動追加されたエンティティを保護
            manual_entities = [
                entity
                for entity in self.detection_results
                if entity.get("manual", False)
            ]
            logger.info(f"手動追加エンティティを保護: {len(manual_entities)}件")

            logger.info("Presidio解析実行開始...")
            logger.info(f"検出設定エンティティ: {self.settings['entities']}")

            # Presidioで解析を実行（モデル検出）
            entities = self.processor.analyze_pdf(self.current_pdf_path)
            logger.info(f"Presidio解析完了: {len(entities)}件のエンティティを検出")

            # 結果を整形し、オフセットベース座標特定を実行
            new_detection_results = []
            if not self.pdf_document:
                self.pdf_document = fitz.open(self.current_pdf_path)

            # PDFTextLocatorを使用して改行なしテキストとの同期を確保
            from pdf.pdf_locator import PDFTextLocator

            locator = PDFTextLocator(self.pdf_document)
            presidio_text = (
                locator.full_text_no_newlines
            )  # Presidio解析用と同じテキスト

            logger.info(
                f"エンティティフィルタリング開始 (設定エンティティ: {self.settings['entities']})"
            )
            filtered_count = 0
            excluded_symbols_count = 0

            import re

            for entity in entities:
                # エンティティタイプでフィルタリング
                if entity["entity_type"] in self.settings["entities"]:
                    # 単一文字記号の除外フィルタリング
                    entity_text = entity.get("text", "")
                    entity_type = entity.get("entity_type", "")

                    # PROPER_NOUNかつ単一文字かつ記号文字の場合は除外
                    if (
                        entity_type == "PROPER_NOUN"
                        and len(entity_text) == 1
                        and re.match(r"[^\w\s]", entity_text)
                    ):
                        excluded_symbols_count += 1
                        logger.debug(
                            f"単一文字記号を除外: '{entity_text}' (PROPER_NOUN)"
                        )
                        continue

                    filtered_count += 1

                    # オフセットベース座標特定を実行（改行なしオフセットを使用）
                    start_offset = entity.get("start", 0)
                    end_offset = entity.get("end", 0)

                    # PDFTextLocatorの改行なしオフセット座標特定を使用
                    coord_rects_with_pages = locator.locate_pii_by_offset_no_newlines(
                        start_offset, end_offset
                    )

                    if not coord_rects_with_pages:
                        logger.warning(
                            f"オフセットベース座標特定に失敗: '{entity['text']}'"
                        )
                        continue

                    # 最初の矩形をメイン座標として使用
                    main_rect_data = coord_rects_with_pages[0]
                    main_rect = main_rect_data["rect"]
                    main_coordinates = {
                        "x0": float(main_rect.x0),
                        "y0": float(main_rect.y0),
                        "x1": float(main_rect.x1),
                        "y1": float(main_rect.y1),
                    }

                    # 複数行矩形情報を作成
                    line_rects = []
                    for i, rect_data in enumerate(coord_rects_with_pages):
                        rect = rect_data["rect"]
                        line_rects.append(
                            {
                                "rect": {
                                    "x0": float(rect.x0),
                                    "y0": float(rect.y0),
                                    "x1": float(rect.x1),
                                    "y1": float(rect.y1),
                                },
                                "coord_space": "fitz",  # フロント側でY反転して描画
                                "text": entity["text"],  # 簡略化
                                "line_number": i + 1,
                                "page_num": rect_data["page_num"],
                            }
                        )

                    result = {
                        "entity_type": str(entity.get("entity_type", "UNKNOWN")),
                        "text": str(entity.get("text", "")),
                        "score": float(entity.get("score", 0.0)),
                        "page": main_rect_data["page_num"],
                        "page_num": main_rect_data[
                            "page_num"
                        ],  # フロントエンド用0ベースページ番号
                        "recognition_metadata": entity.get("recognition_metadata", {}),
                        "analysis_explanation": entity.get("analysis_explanation", {}),
                        "location_info": {
                            "line_number": entity.get("position_details", {}).get(
                                "line_number"
                            ),
                            "word_index": entity.get("position_details", {}).get(
                                "word_index"
                            ),
                        },
                        "start_char": entity.get("position_details", {}).get(
                            "start_char"
                        ),
                        "end_char": entity.get("position_details", {}).get("end_char"),
                        "start": int(entity.get("start", 0)),
                        "end": int(entity.get("end", 0)),
                        "coordinates": main_coordinates,  # Fitz系（x右向き / y下向き）
                        "rect_pdf": [
                            float(main_rect.x0),
                            float(main_rect.y0),
                            float(main_rect.x1),
                            float(main_rect.y1),
                        ],  # Web側はrect_pdfを優先使用（Fitz系）
                        "line_rects": line_rects,
                        "manual": False,  # 自動検出フラグ
                    }

                    # Web側では逐次の独自重複チェックは行わず、後段でCLIロジックに一括委譲
                    new_detection_results.append(result)

            # CLI版の重複除去ロジック（共通API）を使用（設定で有効な場合）
            if self.settings.get("deduplication_enabled", False):
                logger.info(
                    f"CLI版重複除去ロジックを実行: {len(new_detection_results)}件から重複除去開始"
                )
                new_detection_results = self._apply_cli_deduplication(new_detection_results)
                logger.info(f"CLI版重複除去完了: {len(new_detection_results)}件")

            # Analyzer側で追加>モデル>除外を適用済み。ここでは手動分を先頭に結合。
            self.detection_results = manual_entities + new_detection_results

            total_count = len(self.detection_results)
            new_count = len(new_detection_results)
            manual_count = len(manual_entities)

            logger.info(
                f"検出完了: 自動{new_count}件 + 手動{manual_count}件 = 合計{total_count}件"
            )
            if excluded_symbols_count > 0:
                logger.info(f"単一文字記号を除外: {excluded_symbols_count}件")

            return {
                "success": True,
                "message": f"個人情報検出完了 (新規: {new_count}件, 手動保護: {manual_count}件, 合計: {total_count}件)",
                "entities": self.detection_results,
                "count": total_count,
                "new_count": new_count,
                "manual_count": manual_count,
            }

        except Exception as ex:
            logger.error(f"検出処理エラー: {ex}")
            logger.error(traceback.format_exc())
            return {"success": False, "message": f"検出処理に失敗: {str(ex)}"}

    def _apply_additional_patterns(self, locator, full_text_no_newlines: str) -> List[Dict]:
        """追加エンティティ正規表現を全文に適用（追加 > 除外、左高優先・右から適用）。

        - 設定: self.settings["additional_words"] は {ENTITY_TYPE: [regex, ...]} 形式
        - 除外: 追加は除外の影響を受けない（常に保持）
        - 競合: 左（最初）定義が高優先。長さは考慮しない。
        - 座標: PDFTextLocator.locate_pii_by_offset_no_newlines で矩形算出
        """
        import re
        additional = self.settings.get("additional_words", {}) or {}

        # 右→左で探索し、左定義（高優先）順に非重複化
        raw_matches: List[Dict] = []
        order_map: List[tuple] = []  # (entity, idx, pattern)
        for etype, patterns in additional.items():
            if not isinstance(patterns, list):
                continue
            for idx, pat in enumerate(patterns):
                order_map.append((etype, idx, pat))

        for etype, idx, pat in reversed(order_map):
            if not pat:
                continue
            try:
                compiled = re.compile(pat)
            except re.error as e:
                logger.warning(f"無効な追加エンティティ正規表現をスキップ: {pat}: {e}")
                continue
            max_hits = 10000
            hit_count = 0
            for m in compiled.finditer(full_text_no_newlines):
                s, e = m.span()
                if s == e:
                    continue
                raw_matches.append({
                    "start": s,
                    "end": e,
                    "entity_type": etype,
                    "text": full_text_no_newlines[s:e],
                    "_prio": idx,
                })
                hit_count += 1
                if hit_count >= max_hits:
                    logger.warning(f"追加エンティティパターンのヒットが上限({max_hits})に達しました: {pat}")
                    break

        if not raw_matches:
            return []

        # 優先度（idx低い=高優先）で非重複化。長さは無視。
        selected: List[Dict] = []
        occupied: List[tuple] = []
        for m in sorted(raw_matches, key=lambda x: (x["_prio"], x["start"])):
            s, e = m["start"], m["end"]
            if any(not (e <= os or oe <= s) for (os, oe) in occupied):
                continue
            occupied.append((s, e))
            selected.append({k: v for k, v in m.items() if not k.startswith("_")})

        # 位置（矩形）情報の付与
        results: List[Dict] = []
        for ent in selected:
            spans = locator.locate_pii_by_offset_no_newlines(ent["start"], ent["end"])
            if not spans:
                continue
            main = spans[0]
            rect = main["rect"]
            line_rects = []
            for i, r in enumerate(spans):
                rr = r["rect"]
                line_rects.append({
                    "rect": {"x0": float(rr.x0), "y0": float(rr.y0), "x1": float(rr.x1), "y1": float(rr.y1)},
                    "coord_space": "fitz",
                    "text": ent["text"],
                    "line_number": i + 1,
                    "page_num": r["page_num"],
                })

            results.append({
                "entity_type": str(ent.get("entity_type", "UNKNOWN")),
                "text": str(ent.get("text", "")),
                "score": 1.0,
                "page": main["page_num"],
                "page_num": main["page_num"],
                "recognition_metadata": {"recognizer_name": "CustomRegex"},
                "analysis_explanation": {"pattern": "additional_words"},
                "location_info": {},
                "start_char": None,
                "end_char": None,
                "start": int(ent.get("start", 0)),
                "end": int(ent.get("end", 0)),
                "coordinates": {"x0": float(rect.x0), "y0": float(rect.y0), "x1": float(rect.x1), "y1": float(rect.y1)},
                "rect_pdf": [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
                "line_rects": line_rects,
                "manual": False,
                "custom": True,
            })

        # 昇順（開始位置）で返す
        return sorted(results, key=lambda x: x.get("start", 0))

    # 旧Web独自の重複チェックは廃止（CLI委譲に一本化）

    def _calculate_overlap_ratio(self, coords1: Dict, coords2: Dict) -> float:
        """二つの矩形の重複率を計算"""
        try:
            # 矩形1
            x1_min, y1_min = coords1["x0"], coords1["y0"]
            x1_max, y1_max = coords1["x1"], coords1["y1"]

            # 矩形2
            x2_min, y2_min = coords2["x0"], coords2["y0"]
            x2_max, y2_max = coords2["x1"], coords2["y1"]

            # 重複領域を計算
            overlap_x_min = max(x1_min, x2_min)
            overlap_y_min = max(y1_min, y2_min)
            overlap_x_max = min(x1_max, x2_max)
            overlap_y_max = min(y1_max, y2_max)

            if overlap_x_min >= overlap_x_max or overlap_y_min >= overlap_y_max:
                return 0.0  # 重複なし

            # 重複面積
            overlap_area = (overlap_x_max - overlap_x_min) * (
                overlap_y_max - overlap_y_min
            )

            # 各矩形の面積
            area1 = (x1_max - x1_min) * (y1_max - y1_min)
            area2 = (x2_max - x2_min) * (y2_max - y2_min)

            # 小さい方の矩形に対する重複率
            smaller_area = min(area1, area2)
            if smaller_area == 0:
                return 0.0

            return overlap_area / smaller_area

        except Exception as e:
            logger.error(f"重複率計算エラー: {e}")
            return 0.0

    def delete_entity(self, index: int) -> Dict:
        """エンティティを削除"""
        try:
            if 0 <= index < len(self.detection_results):
                deleted_entity = self.detection_results.pop(index)
                logger.info(
                    f"エンティティ削除: {deleted_entity['text']} (タイプ: {deleted_entity['entity_type']})"
                )
                return {
                    "success": True,
                    "message": f"削除完了: {deleted_entity['text']}",
                    "deleted_entity": deleted_entity,
                }
            else:
                return {"success": False, "message": "無効なインデックス"}
        except Exception as e:
            logger.error(f"エンティティ削除エラー: {e}")
            return {"success": False, "message": f"削除エラー: {str(e)}"}



    def _rect_for_entity(self, e, page):
        """エンティティからfitz.Rectを決定する。
        - rect_pdf: PDF座標（最優先）
        - coordinates: 自動検出結果の座標
        """
        try:
            # 1) トップレベルに rect_pdf があれば最優先（手動追加で使用）
            rp = e.get("rect_pdf")
            if isinstance(rp, (list, tuple)) and len(rp) == 4:
                return fitz.Rect(rp)

            # 2) coordinates に x0..y1 (自動検出結果など)
            c = e.get("coordinates") or {}
            if all(k in c for k in ("x0", "y0", "x1", "y1")):
                return fitz.Rect(float(c["x0"]), float(c["y0"]), float(c["x1"]), float(c["y1"]))

            return None
        except Exception as ex:
            logger.debug(f"_rect_for_entity: 変換失敗: {ex}")
            return None

    def _generate_web_annotation_content(self, entity: Dict, mode: str) -> Dict:
        """Web UI用の注釈内容を生成"""
        entity_type_jp = self.get_entity_type_japanese(entity.get("entity_type", "CUSTOM"))
        text = entity.get("text", "")

        if mode == "silent":
            return {"title": "", "content": "", "text": ""}
        elif mode == "minimal":
            return {"title": entity_type_jp, "content": "", "text": f"【{entity_type_jp}】"}
        else:  # verbose
            title = f"個人情報: {entity_type_jp}"
            return {"title": title, "content": text, "text": f"【{entity_type_jp}】\n{text}"}

    def generate_pdf_with_annotations(self, upload_folder: str):
        if not self.current_pdf_path or not self.pdf_document:
            return {"success": False, "message": "PDFファイルが利用できません"}
        os.makedirs(upload_folder, exist_ok=True)
        out_path = os.path.join(
            upload_folder, f"annotated_{uuid.uuid4()}_{os.path.basename(self.current_pdf_path)}"
        )
        shutil.copy2(self.current_pdf_path, out_path)
        doc = fitz.open(out_path)

        # Web UIからの設定を取得（強制的にハイライトのみに統一）
        masking_method = "highlight"
        text_display_mode = self.settings.get("masking_text_mode", "verbose")

        for e in self.detection_results:
            page_idx = int(e.get("page_num", e.get("page", 0)))
            if "page" in e and "page_num" not in e and e.get("source") == "manual":
                page_idx = max(0, page_idx - 1)   # 旧データに1-basedが混在する対策
            if not (0 <= page_idx < len(doc)):
                continue
            page = doc[page_idx]
            rect = self._rect_for_entity(e, page)
            if rect is None or rect.is_empty or rect.is_infinite:
                continue

            color_map = {
                "PERSON": (1,0,0), "LOCATION": (0,1,0), "PHONE_NUMBER": (0,0,1),
                "DATE_TIME": (1,1,0), "INDIVIDUAL_NUMBER": (1,0,1), "YEAR": (0.5,0,1),
                "PROPER_NOUN": (1,0.5,0), "CUSTOM": (0.5,0.5,0.5)
            }
            highlight_color_map = {
                "PERSON": (1,0.8,0.8), "LOCATION": (0.8,1,0.8), "PHONE_NUMBER": (0.8,0.8,1),
                "DATE_TIME": (1,1,0.8), "INDIVIDUAL_NUMBER": (1,0.8,1), "YEAR": (0.8,1,1),
                "PROPER_NOUN": (1,0.86,0.7), "CUSTOM": (0.9,0.9,0.9)
            }
            color = color_map.get(e.get("entity_type"), (0.5, 0.5, 0.5))
            highlight_color = highlight_color_map.get(e.get("entity_type"), (0.9, 0.9, 0.9))

            content = self._generate_web_annotation_content(e, text_display_mode)

            # FreeText注釈は作成しない

            if True:  # ハイライトのみ
                def _to_float(v): return float(v)
                def _fitz_rect_from_any(rect_like, space, page):
                    # dict({x0..}) / list([x0,y0,x1,y1]) / tuple を許容
                    if rect_like is None:
                        return None
                    if isinstance(rect_like, (list, tuple)) and len(rect_like) == 4:
                        x0, y0, x1, y1 = map(_to_float, rect_like)
                    elif isinstance(rect_like, dict) and all(k in rect_like for k in ("x0","y0","x1","y1")):
                        x0 = _to_float(rect_like["x0"]); y0 = _to_float(rect_like["y0"])
                        x1 = _to_float(rect_like["x1"]); y1 = _to_float(rect_like["y1"])
                    else:
                        return None
                    r = fitz.Rect(x0, y0, x1, y1)
                    if space == "pdf":
                        ph = page.rect.height
                        r = fitz.Rect(r.x0, ph - r.y1, r.x1, ph - r.y0)  # Y反転
                    r = r & page.rect
                    if (not r) or r.width <= 0 or r.height <= 0:
                        return None
                    return r

                line_rects = e.get("line_rects") or []
                rects_valid = []
                for lr in line_rects:
                    space = (lr.get("coord_space") or lr.get("space") or "fitz")
                    r = _fitz_rect_from_any(lr.get("rect"), space, page)
                    if r is not None:
                        rects_valid.append(r)

                # 改行またぎ: 字rect群をクレンジング
                rects_valid = self._clean_rects(rects_valid, page)
                if rects_valid:
                    # 1) PyMuPDF>=1.23系は Rect[] を直接受け付ける
                    try:
                        hl = page.add_highlight_annot(rects_valid)
                        hl.set_colors(stroke=highlight_color)
                        hl.set_opacity(0.4)
                        hl.set_info(title=content["title"], content=content["content"])
                        hl.update()
                    except Exception as ex_list:
                        # 2) 互換: Quad[] を試す
                        try:
                            quads = self._merge_into_line_quads(rects_valid)
                            hl = page.add_highlight_annot(quads)
                            hl.set_colors(stroke=highlight_color)
                            hl.set_opacity(0.4)
                            hl.set_info(title=content["title"], content=content["content"])
                            hl.update()
                        except Exception as ex_quad:
                            logger.warning(
                                f"multi-line highlight failed: {type(ex_quad).__name__}: {ex_quad}"
                            )
                            # 3) 最終フォールバック: 行ごとに単発で付与
                            for r in rects_valid:
                                try:
                                    _hl = page.add_highlight_annot(r)
                                    _hl.set_colors(stroke=highlight_color)
                                    _hl.set_opacity(0.4)
                                    _hl.set_info(title=content['title'], content=content['content'])
                                    _hl.update()
                                except Exception as ex_single:
                                    logger.warning(f"single-line highlight failed: {type(ex_single).__name__}: {ex_single}")
                else:
                    # フォールバック：1矩形のみ
                    base_rect = self._rect_for_entity(e, page)
                    if base_rect:
                        try:
                            hl = page.add_highlight_annot(base_rect)
                            hl.set_colors(stroke=highlight_color)
                            hl.set_opacity(0.4)
                            hl.set_info(title=content["title"], content=content["content"])
                            hl.update()
                        except Exception as ex:
                            logger.warning(f"base highlight failed: {type(ex).__name__}: {ex}")

        doc.save(out_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        doc.close()
        return {
            "success": True,
            "filename": os.path.basename(out_path),
            "download_filename": f"masked_{os.path.splitext(os.path.basename(self.current_pdf_path))[0]}.pdf"
        }

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
            if self.processor and self.processor.config_manager and hasattr(self.processor.config_manager, 'should_remove_identical_annotations') and self.processor.config_manager.should_remove_identical_annotations():
                existing_highlights = self._get_existing_highlights(doc)

            highlights_added = 0

            for entity in entities:
                # ★ ページ番号は 0-based（Fitz）を正とする
                page_num = int(entity.get("page_num", entity.get("page", 0)))
                if "page" in entity and "page_num" not in entity and entity.get("source") == "manual":
                    page_num = max(0, page_num - 1)  # 旧1-based混在への防御
                if not (0 <= page_num < len(doc)):
                    continue

                rects_to_highlight = entity.get("line_rects", [])

                if not rects_to_highlight:
                    # ★ 1) 手動追加は rect_pdf（Fitz座標）を最優先で使用
                    rp = entity.get("rect_pdf")
                    if isinstance(rp, (list, tuple)) and len(rp) == 4:
                        rects_to_highlight = [{"rect": fitz.Rect(rp), "page_num": page_num}]
                    else:
                        # 2) 自動検出などの coordinates（x0..y1, page_number=1-based）を使用
                        coords = entity.get("coordinates", {}) or {}
                        if "page_number" in coords:
                            page_num = int(coords.get("page_number", 1)) - 1
                            if not (0 <= page_num < len(doc)):
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
                    rect = rect_info.get("rect")
                    page_num = rect_info.get("page_num")
                    if not isinstance(rect, fitz.Rect):
                        rect = fitz.Rect(rect["x0"], rect["y0"], rect["x1"], rect["y1"])

                    if self._is_duplicate_highlight(
                        rect, entity, existing_highlights, page_num
                    ):
                        logger.debug(
                            f"重複ハイライトをスキップ: {entity['text']} ({entity['entity_type']})"
                        )
                        continue

                    page = doc[page_num]
                    self._add_single_highlight(page, rect, entity)
                    highlights_added += 1

            logger.info(f"追加されたハイライト数: {highlights_added}")
            doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            doc.close()
            return pdf_path

        except Exception as e:
            logger.error(f"ハイライトマスキング中にエラー: {str(e)}")
            raise

    def _clear_all_highlights(self, doc: fitz.Document):
        """PDFから既存の全ハイライトを削除"""
        for page_num in range(len(doc)):
            page = doc[page_num]
            annotations = page.annots()
            annotations_to_remove = []
            
            for annot in annotations:
                if annot.type[1] == "Highlight":
                    annotations_to_remove.append(annot)
            
            for annot in annotations_to_remove:
                page.delete_annot(annot)
    
    def _get_existing_highlights(self, doc: fitz.Document) -> List[Dict]:
        """既存のハイライトを取得"""
        existing_highlights = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            annotations = page.annots()
            
            for annot in annotations:
                if annot.type[1] == "Highlight":
                    rect = annot.rect
                    existing_highlights.append({
                        "rect": rect,
                        "page_num": page_num,
                        "annotation": annot
                    })
        
        return existing_highlights
    
    def _is_duplicate_highlight(
        self, rect: fitz.Rect, entity: Dict, existing_highlights: List[Dict], page_num: int
    ) -> bool:
        """ハイライトの重複をチェック"""
        overlap_threshold = 0.9  # 90%以上の重複で重複と判定
        
        for existing in existing_highlights:
            if existing["page_num"] != page_num:
                continue
                
            existing_rect = existing["rect"]
            
            # 矩形の重複率を計算
            overlap_ratio = self._calculate_rect_overlap_ratio(rect, existing_rect)
            
            if overlap_ratio >= overlap_threshold:
                return True
        
        return False
    
    def _calculate_rect_overlap_ratio(self, rect1: fitz.Rect, rect2: fitz.Rect) -> float:
        """二つのfitz.Rectの重複率を計算"""
        try:
            # 重複領域を計算
            overlap_x_min = max(rect1.x0, rect2.x0)
            overlap_y_min = max(rect1.y0, rect2.y0)
            overlap_x_max = min(rect1.x1, rect2.x1)
            overlap_y_max = min(rect1.y1, rect2.y1)

            if overlap_x_min >= overlap_x_max or overlap_y_min >= overlap_y_max:
                return 0.0  # 重複なし

            # 重複面積
            overlap_area = (overlap_x_max - overlap_x_min) * (overlap_y_max - overlap_y_min)

            # 各矩形の面積
            area1 = (rect1.x1 - rect1.x0) * (rect1.y1 - rect1.y0)
            area2 = (rect2.x1 - rect2.x0) * (rect2.y1 - rect2.y0)

            # 小さい方の矩形に対する重複率
            smaller_area = min(area1, area2)
            if smaller_area == 0:
                return 0.0

            return overlap_area / smaller_area

        except Exception as e:
            logger.error(f"矩形重複率計算エラー: {e}")
            return 0.0
    
    def _add_single_highlight(self, page: fitz.Page, rect: fitz.Rect, entity: Dict):
        """単一のハイライトを追加"""
        try:
            # エンティティタイプに応じた色設定
            highlight_color_map = {
                "PERSON": (1, 0.8, 0.8), "LOCATION": (0.8, 1, 0.8), "PHONE_NUMBER": (0.8, 0.8, 1),
                "DATE_TIME": (1, 1, 0.8), "INDIVIDUAL_NUMBER": (1, 0.8, 1), "YEAR": (0.8, 1, 1),
                "PROPER_NOUN": (1, 0.86, 0.7), "CUSTOM": (0.9, 0.9, 0.9)
            }
            
            highlight_color = highlight_color_map.get(entity.get("entity_type"), (0.9, 0.9, 0.9))
            
            # ハイライト注釈を追加
            hl = page.add_highlight_annot(rect)
            hl.set_colors(stroke=highlight_color)
            hl.set_opacity(0.4)
            
            # 注釈情報を設定
            entity_type_jp = self.get_entity_type_japanese(entity.get("entity_type", "CUSTOM"))
            title = f"個人情報: {entity_type_jp}"
            content = entity.get("text", "")
            
            hl.set_info(title=title, content=content)
            hl.update()
            
        except Exception as e:
            logger.error(f"ハイライト追加エラー: {e}")
            raise

    def _is_duplicate_manual_addition(self, new_entity: Dict) -> bool:
        """手動追加の重複をチェック（手動同士の重複防止）"""
        overlap_threshold = 0.9  # 90%以上の重複で同じ場所と判定（手動はより厳格）

        for existing in self.detection_results:
            # 手動追加のみチェック
            if not existing.get("manual", False):
                continue

            # 同じページ・同じエンティティタイプかチェック
            if (
                existing["page"] == new_entity["page"]
                and existing["entity_type"] == new_entity["entity_type"]
            ):

                # 座標の重複度を計算
                overlap_ratio = self._calculate_overlap_ratio(
                    new_entity["coordinates"], existing["coordinates"]
                )

                if overlap_ratio >= overlap_threshold:
                    return True

        return False

    def _uses_web_deduplication(self) -> bool:
        # 廃止（互換のため残置）
        return False

    def _apply_cli_deduplication(self, entities: List[Dict]) -> List[Dict]:
        """CLIコマンド（codex-duplicate-process）をサブプロセス実行して重複除去。

        - 入力: Web側エンティティ配列 → detect JSONに変換
        - 設定: Web設定 → CLI引数へ変換（必要に応じYAML化も可）
        - 実行: `python -m cli.duplicate_main ...`（stdinにJSONを渡す）
        - 受取: stdoutのJSONを読み取り、_orig_indexで元配列を復元
        """
        import subprocess
        import sys
        import os

        try:
            if not entities:
                return entities

            # overlapの決定（Web設定のcontain_onlyはcontain相当）
            method = str(self.settings.get("deduplication_method", "overlap"))
            overlap_mode = str(self.settings.get("deduplication_overlap_mode", "partial_overlap"))
            if method == "exact":
                overlap = "exact"
            elif method == "contain":
                overlap = "contain"
            else:
                overlap = "contain" if overlap_mode == "contain_only" else "overlap"

            priority = str(self.settings.get("deduplication_priority", "wider_range"))

            # plainエントリを構築（元indexを保持）
            plain = []
            for idx, e in enumerate(entities):
                try:
                    plain.append({
                        "start": int(e.get("start", 0)),
                        "end": int(e.get("end", 0)),
                        "entity": str(e.get("entity_type", "")),
                        "_orig_index": idx,
                    })
                except Exception:
                    continue

            det_in = {"detections": {"plain": plain, "structured": []}}
            import json as _json
            payload = _json.dumps(det_in, ensure_ascii=False)

            # CLI引数を組み立て（stdinから渡す）
            cmd = [sys.executable, "-m", "cli.duplicate_main", "--overlap", overlap]

            if priority == "wider_range":
                cmd += ["--keep", "widest"]
            elif priority == "narrower_range":
                cmd += ["--tie-break", "length,position", "--length-pref", "short", "--position-pref", "first"]
            elif priority == "entity_type":
                # entity_order は設定（ConfigManager）から取得可能な場合のみ付与
                cmd += ["--tie-break", "entity,position", "--position-pref", "first"]
                try:
                    order = self.processor.config_manager.get_entity_priority_order() if self.processor else []
                except Exception:
                    order = []
                if order:
                    cmd += ["--entity-order", ",".join(order)]

            # PYTHONPATHにsrcを追加して -m 実行を安定化
            env = os.environ.copy()
            src_path = os.path.join(os.getcwd(), "src")
            env["PYTHONPATH"] = (src_path + os.pathsep + env.get("PYTHONPATH", "")).strip(os.pathsep)

            proc = subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                input=payload,
                encoding="utf-8",
            )

            if proc.returncode != 0:
                logger.error(f"codex-duplicate-process 失敗: rc={proc.returncode}\nSTDERR:\n{proc.stderr}")
                return entities

            # 出力JSONを解析して _orig_index から元配列を復元
            import json as _json
            try:
                out_obj = _json.loads(proc.stdout)
            except Exception as e:
                logger.error(f"CLI出力のJSONパースに失敗: {e}\n出力=\n{proc.stdout[:1000]}")
                return entities

            keep_idxs = []
            for d in (out_obj.get("detections", {}).get("plain", []) or []):
                oi = d.get("_orig_index")
                if isinstance(oi, int):
                    keep_idxs.append(oi)
            keep_set = set(keep_idxs)
            return [entities[i] for i in range(len(entities)) if i in keep_set]

        except Exception as e:
            logger.error(f"CLI重複除去実行エラー: {e}")
            return entities
        finally:
            pass

    def get_entity_type_japanese(self, entity_type: str) -> str:
        """エンティティタイプの日本語名を返す"""
        mapping = {
            "PERSON": "人名",
            "LOCATION": "場所",
            "PHONE_NUMBER": "電話番号",
            "DATE_TIME": "日時",
            "INDIVIDUAL_NUMBER": "個人番号",
            "YEAR": "年号",
            "PROPER_NOUN": "固有名詞",
            "CUSTOM": "カスタム",
        }
        return mapping.get(entity_type, entity_type)

    # --- rectユーティリティ ---
    @staticmethod
    def _clean_rects(rects, page, min_w=0.8, min_h=0.8):
        cleaned = []
        for r in rects or []:
            try:
                R = fitz.Rect(r).normalize()
            except Exception:
                continue
            if R.is_empty:
                continue
            # ページ外はクリップ
            R = R & page.rect
            if R.width < min_w or R.height < min_h:
                continue
            cleaned.append(R)
        return cleaned

    @staticmethod
    def _merge_into_line_quads(rects, x_gap_tol=1.5):
        """字単位rect群 -> 行単位rect群 -> Quad配列"""
        if not rects:
            return []
        rects = sorted(rects, key=lambda r: (round(r.y0, 1), r.x0))
        groups = []
        cur = [rects[0]]
        gy0, gy1 = rects[0].y0, rects[0].y1
        for r in rects[1:]:
            vov = min(gy1, r.y1) - max(gy0, r.y0)  # 縦方向オーバーラップ
            if vov >= min(r.height, gy1 - gy0) * 0.5:
                cur.append(r)
                gy0, gy1 = min(gy0, r.y0), max(gy1, r.y1)
            else:
                groups.append(cur)
                cur = [r]
                gy0, gy1 = r.y0, r.y1
        groups.append(cur)

        merged = []
        for g in groups:
            g = sorted(g, key=lambda r: r.x0)
            run = g[0]
            for r in g[1:]:
                gap = r.x0 - run.x1
                if gap <= x_gap_tol:  # 近接は結合
                    run = fitz.Rect(min(run.x0, r.x0), min(run.y0, r.y0),
                                    max(run.x1, r.x1), max(run.y1, r.y1))
                else:
                    merged.append(run)
                    run = r
            merged.append(run)
        return [fitz.Quad(r) for r in merged]
