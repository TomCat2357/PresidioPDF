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
PRESIDIO_AVAILABLE = False

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
            "entities": ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
            "masking_method": "highlight"  # highlight, annotation, both
        }
        
        # Presidio プロセッサーの初期化
        self.processor = None
        if PRESIDIO_AVAILABLE:
            try:
                # デフォルトの設定ファイルパスを解決
                base_dir = os.path.dirname(os.path.abspath(__file__))
                config_path = os.path.join(base_dir, '..', 'config_template.yaml')

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
            
                self.processor = PDFPresidioProcessor(config_manager)
                
                mode_str = "GPU" if self.use_gpu else "CPU"
                logger.info(f"Presidio processor初期化完了 ({mode_str}モード)")
            except Exception as e:
                logger.error(f"Presidio processor初期化エラー: {e}")
                self.processor = None
        
        logger.info(f"セッション {session_id} 初期化完了 ({'GPU' if self.use_gpu else 'CPU'}モード)")
    
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
        """個人情報検出処理を実行"""
        try:
            logger.info(f"個人情報検出開始: {self.current_pdf_path}")
            
            if not self.processor or not PRESIDIO_AVAILABLE:
                logger.error("Presidio processorが利用できません。")
                return {"success": False, "message": "サーバーエラー: 検出エンジンが利用できません。"}

            # 手動追加されたエンティティを保護
            manual_entities = [entity for entity in self.detection_results if entity.get("manual", False)]
            logger.info(f"手動追加エンティティを保護: {len(manual_entities)}件")

            # Presidioで解析を実行
            entities = self.processor.analyze_pdf(self.current_pdf_path)
            
            # 結果を整形し、座標を再確認
            new_detection_results = []
            if not self.pdf_document:
                self.pdf_document = fitz.open(self.current_pdf_path)

            for entity in entities:
                page_num = entity.get("page_info", {}).get("page_number", 1)
                page = self.pdf_document[page_num - 1]
                
                # テキスト検索で座標を再取得
                text_instances = page.search_for(entity['text'])
                
                if not text_instances:
                    logger.warning(f"座標が見つかりませんでした: '{entity['text']}' on page {page_num}")
                    continue

                rect = text_instances[0]  # 最初の出現位置の座標を使用

                # エンティティタイプでフィルタリング（閾値チェックを削除）
                if entity['entity_type'] in self.settings['entities']:
                    
                    # 複数行矩形情報を取得
                    line_rects = []
                    if hasattr(self, 'processor') and self.processor:
                        try:
                            line_rects = self.processor._get_text_line_rects(
                                page, entity['text'], 0, len(entity['text'])
                            )
                        except Exception as e:
                            logger.debug(f"複数行矩形取得エラー: {e}")

                    result = {
                        "entity_type": str(entity.get("entity_type", "UNKNOWN")),
                        "text": str(entity.get("text", "")),
                        "page": page_num,
                        # 詳細な位置情報を追加
                        "start_page": entity.get('position_details', {}).get('start_page'),
                        "start_line": entity.get('position_details', {}).get('start_line'),
                        "start_char": entity.get('position_details', {}).get('start_char'),
                        "end_page": entity.get('position_details', {}).get('end_page'),
                        "end_line": entity.get('position_details', {}).get('end_line'),
                        "end_char": entity.get('position_details', {}).get('end_char'),
                        "start": int(entity.get("start", 0)),
                        "end": int(entity.get("end", 0)),
                        "coordinates": {
                            "x0": float(rect.x0),
                            "y0": float(rect.y0),
                            "x1": float(rect.x1),
                            "y1": float(rect.y1)
                        },
                        "line_rects": line_rects,
                        "manual": False  # 自動検出フラグ
                    }
                    
                    # 重複チェック：同じ場所・同じタイプの自動検出を防ぐ
                    if not self._is_duplicate_auto_detection(result, new_detection_results):
                        new_detection_results.append(result)
                    else:
                        logger.info(f"重複検出をスキップ: {result['text']} ({result['entity_type']}) on page {page_num}")

            # 手動追加エンティティと新しい自動検出結果を統合
            self.detection_results = manual_entities + new_detection_results
            
            total_count = len(self.detection_results)
            new_count = len(new_detection_results)
            manual_count = len(manual_entities)
            
            logger.info(f"検出完了: 自動{new_count}件 + 手動{manual_count}件 = 合計{total_count}件")
            
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
                coords = entity.get('coordinates')
                if not (coords and all(k in coords for k in ['x0', 'y0', 'x1', 'y1'])):
                    continue

                rect = fitz.Rect(coords['x0'], coords['y0'], coords['x1'], coords['y1'])
                
                color_map = {
                    'PERSON': (1, 0.8, 0.8),
                    'LOCATION': (0.8, 1, 0.8),
                    'PHONE_NUMBER': (0.8, 0.8, 1),
                    'DATE_TIME': (1, 1, 0.8),
                    'CUSTOM': (0.9, 0.9, 0.9)
                }
                color = color_map.get(entity['entity_type'], (0.9, 0.9, 0.9))
                
                masking_method = self.settings.get("masking_method", "highlight")
                
                if masking_method in ["highlight", "both"]:
                    highlight = page.add_highlight_annot(rect)
                    highlight.set_colors(stroke=color)
                    highlight.set_info(title=f"{self.get_entity_type_japanese(entity['entity_type'])}",
                                       content=f"テキスト: {entity['text']}")
                    highlight.update()

                if masking_method in ["annotation", "both"]:
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
    
    def get_entity_type_japanese(self, entity_type: str) -> str:
        """エンティティタイプの日本語名を返す"""
        mapping = {
            "PERSON": "人名",
            "LOCATION": "場所", 
            "PHONE_NUMBER": "電話番号",
            "DATE_TIME": "日時",
            "CUSTOM": "カスタム"
        }
        return mapping.get(entity_type, entity_type)