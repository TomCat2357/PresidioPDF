#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - Webアプリケーションコア処理
"""

import os
import json
import uuid
import logging
import traceback
import shutil
from datetime import datetime
from typing import List, Dict, Optional
import fitz  # PyMuPDF

# 自プロジェクトのモジュールをインポート
from config_manager import ConfigManager
from pdf_processor import PDFProcessor

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
            "entities": ["PERSON", "LOCATION", "DATE_TIME", "PHONE_NUMBER", "INDIVIDUAL_NUMBER", "YEAR", "PROPER_NOUN"],
            "masking_method": "highlight",  # highlight, annotation, both
            "spacy_model": "ja_core_news_md",
            # 重複除去設定（CLI版と同様）
            "deduplication_enabled": False,
            "deduplication_method": "overlap",  # exact, contain, overlap
            "deduplication_priority": "wider_range",  # wider_range, narrower_range, entity_type
            "deduplication_overlap_mode": "partial_overlap"  # contain_only, partial_overlap
        }
        
        # Presidio プロセッサーの初期化
        self.processor = None
        if PRESIDIO_AVAILABLE:
            try:
                # デフォルトの設定ファイルパスを解決
                config_path = os.path.join(os.getcwd(), 'config.yaml')

                if os.path.exists(config_path):
                    config_manager = ConfigManager(config_file=config_path)
                    logger.info(f"設定ファイルを使用して初期化: {config_path}")
                else:
                    config_manager = ConfigManager()
                    logger.warning(f"設定ファイルが見つかりません: {config_path}。デフォルト設定で初期化します。")
                
                # CPU/GPUモードの設定
                if not self.use_gpu:
                    # CPUモード強制のため、設定を上書き
                    config_manager.spacy_model = getattr(config_manager, 'spacy_model', 'ja_core_news_sm')
                    logger.info(f"CPUモードで初期化中: spaCyモデル = {config_manager.spacy_model}")
            
                self.processor = PDFProcessor(config_manager)
                
                mode_str = "GPU" if self.use_gpu else "CPU"
                logger.info(f"Presidio processor初期化完了 ({mode_str}モード)")
            except Exception as e:
                logger.error(f"Presidio processor初期化エラー: {e}")
                self.processor = None
        
        logger.info(f"セッション {session_id} 初期化完了 ({'GPU' if self.use_gpu else 'CPU'}モード)")
    
    def _reinitialize_processor_with_model(self, spacy_model: str):
        """指定されたspaCyモデルでプロセッサを再初期化"""
        try:
            logger.info(f"プロセッサを再初期化: {spacy_model}")
            
            # 既存のプロセッサを破棄
            if self.processor:
                self.processor = None
            
            # 新しい設定でプロセッサを初期化
            config_path = os.path.join(os.getcwd(), 'config.yaml')
            
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
                config_manager.set_spacy_model('ja_core_news_sm')
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
                "filename": os.path.basename(file_path)
            }
            
        except Exception as ex:
            logger.error(f"PDFファイル読み込みエラー: {ex}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"PDFファイルの読み込みに失敗: {str(ex)}"
            }

    def run_detection(self) -> Dict:
        """個人情報検出処理を実行（オフセットベース座標特定）"""
        try:
            logger.info(f"=== run_detection開始 ===")
            logger.info(f"PDF path: {self.current_pdf_path}")
            logger.info(f"Processor存在: {self.processor is not None}")
            logger.info(f"PRESIDIO_AVAILABLE: {PRESIDIO_AVAILABLE}")
            
            if not self.processor or not PRESIDIO_AVAILABLE:
                logger.error("Presidio processorが利用できません。")
                return {"success": False, "message": "サーバーエラー: 検出エンジンが利用できません。"}

            # 手動追加されたエンティティを保護
            manual_entities = [entity for entity in self.detection_results if entity.get("manual", False)]
            logger.info(f"手動追加エンティティを保護: {len(manual_entities)}件")

            logger.info("Presidio解析実行開始...")
            logger.info(f"検出設定エンティティ: {self.settings['entities']}")
            
            # Presidioで解析を実行
            entities = self.processor.analyze_pdf(self.current_pdf_path)
            logger.info(f"Presidio解析完了: {len(entities)}件のエンティティを検出")
            
            # 結果を整形し、オフセットベース座標特定を実行
            new_detection_results = []
            if not self.pdf_document:
                self.pdf_document = fitz.open(self.current_pdf_path)

            # PDFTextLocatorを使用して改行なしテキストとの同期を確保
            from pdf_locator import PDFTextLocator
            locator = PDFTextLocator(self.pdf_document)
            presidio_text = locator.full_text_no_newlines  # Presidio解析用と同じテキスト

            logger.info(f"エンティティフィルタリング開始 (設定エンティティ: {self.settings['entities']})")
            filtered_count = 0
            excluded_symbols_count = 0
            
            import re
            
            for entity in entities:
                # エンティティタイプでフィルタリング
                if entity['entity_type'] in self.settings['entities']:
                    
                    # 単一文字記号の除外フィルタリング
                    entity_text = entity.get('text', '')
                    entity_type = entity.get('entity_type', '')
                    
                    # PROPER_NOUNかつ単一文字かつ記号文字の場合は除外
                    if (entity_type == 'PROPER_NOUN' and 
                        len(entity_text) == 1 and 
                        re.match(r'[^\w\s]', entity_text)):
                        excluded_symbols_count += 1
                        logger.debug(f"単一文字記号を除外: '{entity_text}' (PROPER_NOUN)")
                        continue
                    
                    filtered_count += 1
                    
                    # オフセットベース座標特定を実行（改行なしオフセットを使用）
                    start_offset = entity.get("start", 0)
                    end_offset = entity.get("end", 0)
                    
                    # PDFTextLocatorの改行なしオフセット座標特定を使用
                    coord_rects_with_pages = locator.locate_pii_by_offset_no_newlines(start_offset, end_offset)
                    
                    if not coord_rects_with_pages:
                        logger.warning(f"オフセットベース座標特定に失敗: '{entity['text']}'")
                        continue
                    
                    # 最初の矩形をメイン座標として使用
                    main_rect_data = coord_rects_with_pages[0]
                    main_rect = main_rect_data['rect']
                    main_coordinates = {
                        'x0': float(main_rect.x0),
                        'y0': float(main_rect.y0),
                        'x1': float(main_rect.x1),
                        'y1': float(main_rect.y1)
                    }
                    
                    # 複数行矩形情報を作成
                    line_rects = []
                    for i, rect_data in enumerate(coord_rects_with_pages):
                        rect = rect_data['rect']
                        line_rects.append({
                            'rect': {
                                'x0': float(rect.x0),
                                'y0': float(rect.y0),
                                'x1': float(rect.x1),
                                'y1': float(rect.y1)
                            },
                            'text': entity['text'],  # 簡略化
                            'line_number': i + 1,
                            'page_num': rect_data['page_num']
                        })
                    
                    result = {
                        "entity_type": str(entity.get("entity_type", "UNKNOWN")),
                        "text": str(entity.get("text", "")),
                        "score": float(entity.get("score", 0.0)),
                        "page": main_rect_data['page_num'],
                        "recognition_metadata": entity.get("recognition_metadata", {}),
                        "analysis_explanation": entity.get("analysis_explanation", {}),
                        "location_info": {
                            "line_number": entity.get('position_details', {}).get('line_number'),
                            "word_index": entity.get('position_details', {}).get('word_index'),
                        },
                        "start_char": entity.get('position_details', {}).get('start_char'),
                        "end_char": entity.get('position_details', {}).get('end_char'),
                        "start": int(entity.get("start", 0)),
                        "end": int(entity.get("end", 0)),
                        "coordinates": main_coordinates,
                        "line_rects": line_rects,
                        "manual": False  # 自動検出フラグ
                    }
                    
                    # Web版独自の重複チェック（従来の処理）を設定に応じて実行
                    if self.settings.get("deduplication_enabled", False) and self._uses_web_deduplication():
                        if not self._is_duplicate_auto_detection(result, new_detection_results):
                            new_detection_results.append(result)
                        else:
                            logger.info(f"Web版重複検出をスキップ: {result['text']} ({result['entity_type']}) on page {result['page']}")
                    else:
                        # 重複チェックを行わない（または後でCLI版の方式で実行）
                        new_detection_results.append(result)

            # CLI版の重複除去ロジックを使用（設定で有効な場合）
            if self.settings.get("deduplication_enabled", False) and not self._uses_web_deduplication():
                logger.info(f"CLI版重複除去ロジックを実行: {len(new_detection_results)}件から重複除去開始")
                new_detection_results = self._apply_cli_deduplication(new_detection_results)
                logger.info(f"CLI版重複除去完了: {len(new_detection_results)}件")

            # 手動追加エンティティと新しい自動検出結果を統合
            self.detection_results = manual_entities + new_detection_results
            
            total_count = len(self.detection_results)
            new_count = len(new_detection_results)
            manual_count = len(manual_entities)
            
            logger.info(f"検出完了: 自動{new_count}件 + 手動{manual_count}件 = 合計{total_count}件")
            if excluded_symbols_count > 0:
                logger.info(f"単一文字記号を除外: {excluded_symbols_count}件")
            
            return {
                "success": True,
                "message": f"個人情報検出完了 (新規: {new_count}件, 手動保護: {manual_count}件, 合計: {total_count}件)",
                "results": self.detection_results,
                "count": total_count,
                "new_count": new_count,
                "manual_count": manual_count
            }
            
        except Exception as ex:
            logger.error(f"検出処理エラー: {ex}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"検出処理に失敗: {str(ex)}"
            }

    def _is_duplicate_auto_detection(self, new_entity: Dict, existing_entities: List[Dict]) -> bool:
        """自動検出の重複をチェック（同じ場所・同じタイプ）"""
        overlap_threshold = 0.8  # 80%以上の重複で同じ場所と判定
        
        for existing in existing_entities:
            # 手動追加は重複チェック対象外
            if existing.get("manual", False):
                continue
                
            # 同じページ・同じエンティティタイプかチェック
            if (existing["page"] == new_entity["page"] and 
                existing["entity_type"] == new_entity["entity_type"]):
                
                # 座標の重複度を計算
                overlap_ratio = self._calculate_overlap_ratio(
                    new_entity["coordinates"], existing["coordinates"]
                )
                
                if overlap_ratio >= overlap_threshold:
                    return True
        
        return False
    
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
            overlap_area = (overlap_x_max - overlap_x_min) * (overlap_y_max - overlap_y_min)
            
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
                logger.info(f"エンティティ削除: {deleted_entity['text']} (タイプ: {deleted_entity['entity_type']})")
                return {
                    "success": True,
                    "message": f"削除完了: {deleted_entity['text']}",
                    "deleted_entity": deleted_entity
                }
            else:
                return {
                    "success": False,
                    "message": "無効なインデックス"
                }
        except Exception as e:
            logger.error(f"エンティティ削除エラー: {e}")
            return {
                "success": False,
                "message": f"削除エラー: {str(e)}"
            }
    
    def generate_pdf_with_annotations(self, upload_folder: str) -> Dict:
        """現在の検出結果をアノテーション/ハイライトとしてPDFに適用し、ダウンロード用のパスを返す"""
        if not self.current_pdf_path or not self.pdf_document:
            return {
                "success": False,
                "message": "PDFファイルが利用できません"
            }
        
        try:
            logger.info(f"PDF保存用アノテーション適用開始: {self.current_pdf_path}")
            
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder, exist_ok=True)
            
            temp_pdf_path = os.path.join(
                upload_folder, 
                f"annotated_{uuid.uuid4()}_{os.path.basename(self.current_pdf_path)}"
            )
            
            # 元のドキュメントをコピーして作業する
            shutil.copy2(self.current_pdf_path, temp_pdf_path)
            
            new_doc = fitz.open(temp_pdf_path)

            for entity in self.detection_results:
                page_num = entity.get('page', 1) - 1
                if page_num >= len(new_doc):
                    continue
                
                page = new_doc[page_num]
                
                # line_rectsを優先的に使用（複数行対応）
                line_rects = entity.get('line_rects', [])
                if line_rects:
                    # 複数行エンティティの場合は各行に対してハイライトを追加
                    rects_to_process = []
                    for line_rect in line_rects:
                        rect_data = line_rect.get('rect')
                        if rect_data and all(k in rect_data for k in ['x0', 'y0', 'x1', 'y1']):
                            rects_to_process.append(fitz.Rect(rect_data['x0'], rect_data['y0'], rect_data['x1'], rect_data['y1']))
                else:
                    # 単一行エンティティの場合は従来通り
                    coords = entity.get('coordinates')
                    if coords and all(k in coords for k in ['x0', 'y0', 'x1', 'y1']):
                        rects_to_process = [fitz.Rect(coords['x0'], coords['y0'], coords['x1'], coords['y1'])]
                    else:
                        continue
                
                if not rects_to_process:
                    continue

                color_map = {
                    'PERSON': (1, 0.8, 0.8),
                    'LOCATION': (0.8, 1, 0.8),
                    'PHONE_NUMBER': (0.8, 0.8, 1),
                    'DATE_TIME': (1, 1, 0.8),
                    'INDIVIDUAL_NUMBER': (1, 0.8, 1),
                    'YEAR': (0.8, 1, 1),
                    'PROPER_NOUN': (1, 0.86, 0.7),
                    'CUSTOM': (0.9, 0.9, 0.9)
                }
                color = color_map.get(entity['entity_type'], (0.9, 0.9, 0.9))
                
                masking_method = self.settings.get("masking_method", "highlight")
                
                # 全ての矩形に対してハイライト/アノテーションを適用
                for rect_index, rect in enumerate(rects_to_process):
                    if masking_method in ["highlight", "both"]:
                        highlight = page.add_highlight_annot(rect)
                        highlight.set_colors(stroke=color)
                        # 最初の矩形のみにタイトル情報を設定（重複回避）
                        if rect_index == 0:
                            highlight.set_info(title=f"{self.get_entity_type_japanese(entity['entity_type'])}",
                                               content=f"テキスト: {entity['text']}")
                        else:
                            highlight.set_info(title=f"{self.get_entity_type_japanese(entity['entity_type'])} (続き)",
                                               content=f"テキスト: {entity['text']} (行 {rect_index + 1})")
                        highlight.update()

                    if masking_method in ["annotation", "both"]:
                        # アノテーションは最初の矩形のみに追加（重複回避）
                        if rect_index == 0:
                            annotation = page.add_text_annot(rect.tl, f"{self.get_entity_type_japanese(entity['entity_type'])}")
                            annotation.set_info(title="個人情報検出", content=f"タイプ: {entity['entity_type']}\\nテキスト: {entity['text']}")
                            annotation.update()
            
            new_doc.saveIncr() # 変更を追記保存
            new_doc.close()
            
            if os.path.exists(temp_pdf_path):
                file_size = os.path.getsize(temp_pdf_path)
                logger.info(f"PDF保存用ファイル生成完了: {temp_pdf_path} (サイズ: {file_size} bytes)")
            else:
                raise IOError("PDFファイルの生成に失敗しました（ファイルが作成されませんでした）")
            
            return {
                "success": True,
                "message": f"PDF保存用ファイル生成完了: {os.path.basename(temp_pdf_path)}",
                "output_path": temp_pdf_path,
                "filename": os.path.basename(temp_pdf_path),
                "download_filename": f"masked_{os.path.splitext(os.path.basename(self.current_pdf_path))[0]}.pdf"
            }
            
        except Exception as e:
            logger.error(f"PDF保存用ファイル生成エラー: {e}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"PDF保存用ファイルの生成に失敗: {str(e)}"
            }

    def _is_duplicate_manual_addition(self, new_entity: Dict) -> bool:
        """手動追加の重複をチェック（手動同士の重複防止）"""
        overlap_threshold = 0.9  # 90%以上の重複で同じ場所と判定（手動はより厳格）
        
        for existing in self.detection_results:
            # 手動追加のみチェック
            if not existing.get("manual", False):
                continue
                
            # 同じページ・同じエンティティタイプかチェック
            if (existing["page"] == new_entity["page"] and 
                existing["entity_type"] == new_entity["entity_type"]):
                
                # 座標の重複度を計算
                overlap_ratio = self._calculate_overlap_ratio(
                    new_entity["coordinates"], existing["coordinates"]
                )
                
                if overlap_ratio >= overlap_threshold:
                    return True
        
        return False
    
    def _uses_web_deduplication(self) -> bool:
        """Web版独自の重複除去を使用するかを判定"""
        # Web版独自の重複除去は基本的に座標ベースの処理に特化
        # CLI版の方が高機能なため、基本的にはCLI版を推奨
        return False  # 常にCLI版の重複除去を使用
    
    def _apply_cli_deduplication(self, entities: List[Dict]) -> List[Dict]:
        """CLI版の重複除去ロジックを適用"""
        try:
            if not entities:
                return entities
            
            # analyzer.pyの重複除去ロジックを再現
            return self._deduplicate_entities_cli_style(entities)
            
        except Exception as e:
            logger.error(f"CLI版重複除去エラー: {e}")
            return entities
    
    def _deduplicate_entities_cli_style(self, entities: List[Dict]) -> List[Dict]:
        """CLI版と同じ重複除去ロジック（analyzer.pyから移植）"""
        if not entities:
            return entities
        
        method = self.settings.get("deduplication_method", "overlap")
        priority = self.settings.get("deduplication_priority", "wider_range")
        
        sorted_entities = sorted(entities, key=lambda x: x.get('start', 0))
        deduplicated = []
        
        for current_entity in sorted_entities:
            should_add = True
            entities_to_remove = []
            
            for i, existing_entity in enumerate(deduplicated):
                if self._has_overlap_cli_style(current_entity, existing_entity, method):
                    current_should_win = self._should_current_entity_win_cli_style(
                        current_entity, existing_entity, priority)
                    
                    if current_should_win:
                        entities_to_remove.append(i)
                    else:
                        should_add = False
                        break
            
            for i in sorted(entities_to_remove, reverse=True):
                removed_entity = deduplicated.pop(i)
                logger.debug(f"CLI版重複除去: '{removed_entity['text']}' ({removed_entity['entity_type']}) を除去")
            
            if should_add:
                deduplicated.append(current_entity)
            else:
                logger.debug(f"CLI版重複除去: '{current_entity['text']}' ({current_entity['entity_type']}) を除去")
        
        original_count = len(entities)
        deduplicated_count = len(deduplicated)
        if original_count != deduplicated_count:
            logger.info(f"CLI版重複除去: {original_count}件 → {deduplicated_count}件 ({original_count - deduplicated_count}件を除去)")
        
        return deduplicated
    
    def _has_overlap_cli_style(self, entity1: Dict, entity2: Dict, method: str) -> bool:
        """CLI版の重複判定（analyzer.pyから移植）"""
        start1, end1 = entity1.get('start', 0), entity1.get('end', 0)
        start2, end2 = entity2.get('start', 0), entity2.get('end', 0)
        
        if method == "exact":
            return start1 == start2 and end1 == end2
        elif method == "contain":
            return (start1 <= start2 and end1 >= end2) or (start2 <= start1 and end2 >= end1)
        elif method == "overlap":
            overlap_mode = self.settings.get("deduplication_overlap_mode", "partial_overlap")
            
            if overlap_mode == "contain_only":
                return (start1 <= start2 and end1 >= end2) or (start2 <= start1 and end2 >= end1)
            elif overlap_mode == "partial_overlap":
                return not (end1 <= start2 or end2 <= start1)
            else:
                logger.warning(f"不明な重複モード: {overlap_mode}. デフォルトのpartial_overlapを使用します。")
                return not (end1 <= start2 or end2 <= start1)
        else:
            logger.warning(f"不明な重複判定方法: {method}. デフォルトのoverlapを使用します。")
            return not (end1 <= start2 or end2 <= start1)
    
    def _should_current_entity_win_cli_style(self, current_entity: Dict, existing_entity: Dict, priority: str) -> bool:
        """CLI版の優先度判定（analyzer.pyから移植）"""
        if priority == "wider_range":
            current_range = current_entity.get('end', 0) - current_entity.get('start', 0)
            existing_range = existing_entity.get('end', 0) - existing_entity.get('start', 0)
            if current_range != existing_range:
                return current_range > existing_range
            return current_entity.get('start', 0) < existing_entity.get('start', 0)

        elif priority == "narrower_range":
            current_range = current_entity.get('end', 0) - current_entity.get('start', 0)
            existing_range = existing_entity.get('end', 0) - existing_entity.get('start', 0)
            if current_range != existing_range:
                return current_range < existing_range
            return current_entity.get('start', 0) < existing_entity.get('start', 0)

        elif priority == "entity_type":
            # デフォルトの優先順位
            entity_order = ["INDIVIDUAL_NUMBER", "PHONE_NUMBER", "PERSON", "LOCATION", "DATE_TIME", "YEAR", "PROPER_NOUN"]
            try:
                current_priority = entity_order.index(current_entity.get('entity_type', ''))
            except ValueError:
                current_priority = len(entity_order)
            
            try:
                existing_priority = entity_order.index(existing_entity.get('entity_type', ''))
            except ValueError:
                existing_priority = len(entity_order)
            
            if current_priority != existing_priority:
                return current_priority < existing_priority
            return current_entity.get('start', 0) < existing_entity.get('start', 0)
        
        else:
            # デフォルト: wider_range
            current_range = current_entity.get('end', 0) - current_entity.get('start', 0)
            existing_range = existing_entity.get('end', 0) - existing_entity.get('start', 0)
            if current_range != existing_range:
                return current_range > existing_range
            return current_entity.get('start', 0) < existing_entity.get('start', 0)

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
            "CUSTOM": "カスタム"
        }
        return mapping.get(entity_type, entity_type)
    
