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
            "entities": ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
            "masking_method": "highlight",  # highlight, annotation, both
            "spacy_model": "ja_core_news_sm"
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
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, '..', 'config_template.yaml')
            
            if os.path.exists(config_path):
                config_manager = ConfigManager(config_file=config_path)
            else:
                config_manager = ConfigManager()
            
            # spaCyモデルを強制設定
            config_manager.spacy_model = spacy_model
            
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
                config_manager.spacy_model = 'ja_core_news_sm'
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
            logger.info(f"個人情報検出開始: {self.current_pdf_path}")
            
            if not self.processor or not PRESIDIO_AVAILABLE:
                logger.error("Presidio processorが利用できません。")
                return {"success": False, "message": "サーバーエラー: 検出エンジンが利用できません。"}

            # 手動追加されたエンティティを保護
            manual_entities = [entity for entity in self.detection_results if entity.get("manual", False)]
            logger.info(f"手動追加エンティティを保護: {len(manual_entities)}件")

            # Presidioで解析を実行
            entities = self.processor.analyze_pdf(self.current_pdf_path)
            
            # 結果を整形し、オフセットベース座標特定を実行
            new_detection_results = []
            if not self.pdf_document:
                self.pdf_document = fitz.open(self.current_pdf_path)

            # 各ページごとに文字-オフセット-座標マッピングを構築
            page_mappings = {}
            for page_num in range(len(self.pdf_document)):
                page_mappings[page_num] = self._build_character_offset_mapping(page_num)

            for entity in entities:
                page_num = entity.get("page_info", {}).get("page_number", 1)
                page_index = page_num - 1  # 0-based index
                
                if page_index not in page_mappings:
                    logger.warning(f"ページマッピングが見つかりません: page {page_num}")
                    continue
                
                # エンティティタイプでフィルタリング
                if entity['entity_type'] in self.settings['entities']:
                    
                    # オフセットベース座標特定を実行
                    start_offset = entity.get("start", 0)
                    end_offset = entity.get("end", 0)
                    
                    coordinate_data = self._locate_pii_by_offset_precise(
                        page_mappings[page_index], start_offset, end_offset, entity['text']
                    )
                    
                    if not coordinate_data:
                        logger.warning(f"オフセットベース座標特定に失敗: '{entity['text']}' on page {page_num}")
                        continue

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
                        "coordinates": coordinate_data['main_coordinates'],
                        "line_rects": coordinate_data['line_rects'],
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
    
    def _build_character_offset_mapping(self, page_index: int) -> Dict:
        """
        指定されたページの文字-オフセット-座標マッピングを構築
        
        Args:
            page_index: ページインデックス（0-based）
            
        Returns:
            Dict: {'full_text': str, 'char_positions': List[Dict]}
        """
        try:
            page = self.pdf_document[page_index]
            textpage = page.get_textpage()
            raw_data = json.loads(textpage.extractRAWJSON())
            
            full_text = ''
            char_positions = []
            char_index = 0
            
            for block in raw_data['blocks']:
                for line in block['lines']:
                    for span in line['spans']:
                        for char_data in span['chars']:
                            char_text = char_data['c']
                            full_text += char_text
                            char_positions.append({
                                'offset': char_index,
                                'char': char_text,
                                'bbox': char_data['bbox']
                            })
                            char_index += 1
                    
                    # 行末に改行を追加
                    full_text += '\n'
                    char_positions.append({
                        'offset': char_index,
                        'char': '\n',
                        'bbox': None  # 改行は座標なし
                    })
                    char_index += 1
            
            logger.debug(f"Page {page_index + 1}: Built character mapping with {len(char_positions)} positions")
            
            return {
                'full_text': full_text,
                'char_positions': char_positions
            }
            
        except Exception as e:
            logger.error(f"文字オフセットマッピング構築エラー (page {page_index + 1}): {e}")
            return {'full_text': '', 'char_positions': []}
    
    def _locate_pii_by_offset_precise(self, page_mapping: Dict, start_offset: int, end_offset: int, pii_text: str) -> Optional[Dict]:
        """
        オフセット範囲から正確な座標データを取得
        
        Args:
            page_mapping: _build_character_offset_mapping()で作成されたマッピング
            start_offset: PII開始オフセット
            end_offset: PII終了オフセット
            pii_text: PII文字列（検証用）
            
        Returns:
            Dict: {'main_coordinates': Dict, 'line_rects': List[Dict]} または None
        """
        try:
            char_positions = page_mapping['char_positions']
            full_text = page_mapping['full_text']
            
            # オフセット範囲の検証
            if start_offset < 0 or end_offset > len(char_positions):
                logger.warning(f"オフセット範囲が無効: {start_offset}-{end_offset} (max: {len(char_positions)})")
                return None
            
            # オフセット範囲のテキストを抽出して検証
            extracted_chars = []
            valid_bboxes = []
            
            for i in range(start_offset, end_offset):
                if i < len(char_positions):
                    char_info = char_positions[i]
                    extracted_chars.append(char_info['char'])
                    
                    # 改行以外の文字の座標を収集
                    if char_info['bbox'] is not None:
                        valid_bboxes.append({
                            'char': char_info['char'],
                            'bbox': char_info['bbox'],
                            'offset': i
                        })
            
            extracted_text = ''.join(extracted_chars)
            
            # テキスト検証（改行を除いて比較）
            pii_normalized = pii_text.replace('\n', '').replace('\r', '')
            extracted_normalized = extracted_text.replace('\n', '').replace('\r', '')
            
            if pii_normalized != extracted_normalized:
                logger.warning(f"テキスト不一致: 期待='{pii_normalized}' 実際='{extracted_normalized}'")
                # 部分的一致でも処理を続行
            
            if not valid_bboxes:
                logger.warning(f"有効な座標が見つかりません: '{pii_text}'")
                return None
            
            # メイン座標（全体の境界矩形）を計算
            all_x0 = [bbox_info['bbox'][0] for bbox_info in valid_bboxes]
            all_y0 = [bbox_info['bbox'][1] for bbox_info in valid_bboxes]
            all_x1 = [bbox_info['bbox'][2] for bbox_info in valid_bboxes]
            all_y1 = [bbox_info['bbox'][3] for bbox_info in valid_bboxes]
            
            main_coordinates = {
                'x0': min(all_x0),
                'y0': min(all_y0),
                'x1': max(all_x1),
                'y1': max(all_y1)
            }
            
            # 複数行矩形を作成（改行を跨ぐPII用）
            line_rects = self._create_line_rects_from_chars(valid_bboxes, extracted_text)
            
            logger.debug(f"オフセット座標特定成功: '{pii_text}' -> {len(line_rects)} rects")
            
            return {
                'main_coordinates': main_coordinates,
                'line_rects': line_rects
            }
            
        except Exception as e:
            logger.error(f"オフセットベース座標特定エラー: {e}")
            return None
    
    def _create_line_rects_from_chars(self, valid_bboxes: List[Dict], extracted_text: str) -> List[Dict]:
        """
        文字座標から行ごとの矩形を作成（改行を跨ぐPII対応）
        
        Args:
            valid_bboxes: 有効な文字座標リスト
            extracted_text: 抽出されたテキスト（改行含む）
            
        Returns:
            List[Dict]: 行ごとの矩形情報
        """
        try:
            if not valid_bboxes:
                return []
            
            # Y座標でグループ化（同じ行の文字をまとめる）
            line_groups = {}
            for bbox_info in valid_bboxes:
                bbox = bbox_info['bbox']
                y_center = (bbox[1] + bbox[3]) / 2  # Y座標の中心
                
                # 近い行をグループ化（±2ピクセル以内）
                found_group = False
                for existing_y in line_groups.keys():
                    if abs(y_center - existing_y) <= 2.0:
                        line_groups[existing_y].append(bbox_info)
                        found_group = True
                        break
                
                if not found_group:
                    line_groups[y_center] = [bbox_info]
            
            # 各行ごとに矩形を作成
            line_rects = []
            for line_y, line_chars in sorted(line_groups.items()):
                if not line_chars:
                    continue
                
                # 行内の文字から境界矩形を計算
                line_x0 = min(char['bbox'][0] for char in line_chars)
                line_y0 = min(char['bbox'][1] for char in line_chars)
                line_x1 = max(char['bbox'][2] for char in line_chars)
                line_y1 = max(char['bbox'][3] for char in line_chars)
                
                # 行のテキストを再構築
                line_text = ''.join(char['char'] for char in sorted(line_chars, key=lambda x: x['bbox'][0]))
                
                line_rect = {
                    'rect': {
                        'x0': line_x0,
                        'y0': line_y0,
                        'x1': line_x1,
                        'y1': line_y1
                    },
                    'text': line_text,
                    'line_number': len(line_rects) + 1  # 1-based line number
                }
                
                line_rects.append(line_rect)
            
            logger.debug(f"複数行矩形作成完了: {len(line_rects)} lines for text '{extracted_text.replace(chr(10), '\\n')}'")
            
            return line_rects
            
        except Exception as e:
            logger.error(f"複数行矩形作成エラー: {e}")
            return []