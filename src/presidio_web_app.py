#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - Webアプリケーション版
"""

from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
import os
import json
import uuid
import logging
import traceback
import sys
from datetime import datetime
from typing import List, Dict, Optional
import io
import base64
from PIL import Image
import fitz  # PyMuPDF

# 自プロジェクトのモジュールをインポート
try:
    from pdf_presidio_processor import PDFPresidioProcessor
    from config_manager import ConfigManager
    PRESIDIO_AVAILABLE = True
except ImportError as e:
    print(f"Presidio processor import failed: {e}")
    PRESIDIO_AVAILABLE = False

# Flask アプリケーションの設定
app = Flask(__name__)
app.secret_key = 'presidio-pdf-web-app-secret-key-' + str(uuid.uuid4())

# アップロード設定
UPLOAD_FOLDER = 'web_uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# アップロードフォルダを作成
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ログ設定
log_filename = f"presidio_web_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# グローバル変数（セッション管理）
sessions = {}

class PresidioPDFWebApp:
    """PDF個人情報マスキングWebアプリケーション"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_pdf_path: Optional[str] = None
        self.detection_results: List[Dict] = []
        self.pdf_document = None
        self.total_pages = 0
        self.settings = {
            "entities": ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
            "threshold": 0.5,
            "masking_method": "highlight"  # highlight, annotation, both
        }
        
        # Presidio プロセッサーの初期化
        self.processor = None
        self.config_file_path = None
        if PRESIDIO_AVAILABLE:
            try:
                default_config_path = os.path.join(os.path.dirname(__file__), "..", "config", "low_threshold.yaml")
                if os.path.exists(default_config_path):
                    config_manager = ConfigManager(config_file=default_config_path)
                    self.config_file_path = default_config_path
                    logger.info(f"デフォルト設定ファイル使用: {default_config_path}")
                else:
                    config_manager = ConfigManager()
                    logger.info("デフォルト設定で初期化")
                
                self.processor = PDFPresidioProcessor(config_manager)
                logger.info("Presidio processor初期化完了")
            except Exception as e:
                logger.error(f"Presidio processor初期化エラー: {e}")
                self.processor = None
        
        logger.info(f"セッション {session_id} 初期化完了")
    
    def load_pdf_file(self, file_path: str) -> Dict:
        """PDFファイルを読み込み"""
        try:
            logger.info(f"PDFファイル読み込み開始: {file_path}")
            self.current_pdf_path = file_path
            self.detection_results = []
            
            # PDFドキュメントを開く
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
            return {
                "success": False,
                "message": f"PDFファイルの読み込みに失敗: {str(ex)}"
            }
    
    def get_pdf_page_image(self, page_num: int, zoom: float = 1.0, show_highlights: bool = False) -> Optional[str]:
        """PDFページを画像として取得（Base64エンコード）"""
        logger.info(f"get_pdf_page_image called: page={page_num}, zoom={zoom}, highlights={show_highlights}")
        logger.info(f"pdf_document exists: {self.pdf_document is not None}")
        logger.info(f"total_pages: {self.total_pages}")
        
        if not self.pdf_document:
            logger.error("PDF document is None")
            return None
            
        if page_num >= self.total_pages:
            logger.error(f"Page number {page_num} >= total pages {self.total_pages}")
            return None
        
        try:
            # ページを取得
            page = self.pdf_document[page_num]
            
            # 検出結果のハイライトを一時的に追加
            temp_annotations = []
            if show_highlights and self.detection_results:
                # 現在のページに対応する検出結果を取得
                page_entities = [
                    entity for entity in self.detection_results 
                    if entity.get('page', 1) == page_num + 1
                ]
                
                for entity in page_entities:
                    try:
                        # 座標情報がある場合は直接使用
                        if 'coordinates' in entity and entity['coordinates']:
                            coords = entity['coordinates']
                            if all(k in coords for k in ['x0', 'y0', 'x1', 'y1']):
                                # 座標から直接矩形を作成
                                rect = fitz.Rect(coords['x0'], coords['y0'], coords['x1'], coords['y1'])
                                logger.debug(f"座標使用: {entity['text']} at {rect}")
                            else:
                                # 座標情報が不完全な場合はテキスト検索
                                text_instances = page.search_for(entity['text'])
                                if not text_instances:
                                    continue
                                rect = text_instances[0]
                                logger.debug(f"テキスト検索: {entity['text']} at {rect}")
                        else:
                            # 座標情報がない場合はテキスト検索
                            text_instances = page.search_for(entity['text'])
                            if not text_instances:
                                continue
                            rect = text_instances[0]
                            logger.debug(f"テキスト検索(フォールバック): {entity['text']} at {rect}")
                        
                        # エンティティタイプに応じて色を設定
                        color_map = {
                            'PERSON': (1, 0.8, 0.8),      # 薄い赤
                            'LOCATION': (0.8, 1, 0.8),    # 薄い緑
                            'PHONE_NUMBER': (0.8, 0.8, 1), # 薄い青
                            'DATE_TIME': (1, 1, 0.8)      # 薄い黄
                        }
                        color = color_map.get(entity['entity_type'], (0.9, 0.9, 0.9))
                        
                        # ハイライト注釈を追加
                        highlight = page.add_highlight_annot(rect)
                        highlight.set_colors(stroke=color)
                        highlight.update()
                        temp_annotations.append(highlight)
                        
                        logger.debug(f"ハイライト追加成功: {entity['text']} ({entity['entity_type']}) at {rect}")
                        
                    except Exception as e:
                        logger.warning(f"ハイライト追加失敗 for {entity['text']}: {e}")
            
            # 拡大率を適用してピクセルマップを取得
            base_resolution = 2.0
            actual_zoom = zoom * base_resolution
            logger.info(f"Zoom calculation: zoom={zoom}, base_resolution={base_resolution}, actual_zoom={actual_zoom}")
            
            mat = fitz.Matrix(actual_zoom, actual_zoom)
            pix = page.get_pixmap(matrix=mat)
            logger.info(f"Generated pixmap size: {pix.width} x {pix.height}")
            
            # PIL Imageに変換
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # 一時的な注釈を削除（表示用のみ）
            for annot in temp_annotations:
                page.delete_annot(annot)
            
            # Base64エンコード
            bio = io.BytesIO()
            img.save(bio, format='PNG')
            img_base64 = base64.b64encode(bio.getvalue()).decode('utf-8')
            
            logger.info(f"ページ画像生成成功: page={page_num}, image_size={len(img_base64)} bytes")
            return img_base64
            
        except Exception as e:
            logger.error(f"ページ画像取得エラー: {e}")
            logger.error(traceback.format_exc())
            return None    
    def run_detection(self) -> Dict:
        """個人情報検出処理を実行"""
        try:
            logger.info(f"個人情報検出開始: {self.current_pdf_path}")
            
            if self.processor and PRESIDIO_AVAILABLE:
                # 実際のPresidio処理を実行
                logger.info("Presidio processorを使用して検出を実行")
                entities = self.processor.analyze_pdf(self.current_pdf_path)
                
                # 結果を変換（JSONシリアライズ可能な形式に）
                self.detection_results = []
                for entity in entities:
                    # JSONシリアライズ可能な基本データのみを抽出
                    result = {
                        "entity_type": str(entity.get("entity_type", "UNKNOWN")),
                        "text": str(entity.get("text", "")),
                        "confidence": float(entity.get("score", 0.0)),
                        "page": int(entity.get("page_info", {}).get("page_number", 1)) if entity.get("page_info") else 1,
                        "start": int(entity.get("start", 0)),
                        "end": int(entity.get("end", 0)),
                        "coordinates": {
                            "x0": float(entity.get("coordinates", {}).get("x0", 0)) if entity.get("coordinates") else 0,
                            "y0": float(entity.get("coordinates", {}).get("y0", 0)) if entity.get("coordinates") else 0,
                            "x1": float(entity.get("coordinates", {}).get("x1", 0)) if entity.get("coordinates") else 0,
                            "y1": float(entity.get("coordinates", {}).get("y1", 0)) if entity.get("coordinates") else 0
                        }
                    }
                    # 元のエンティティ情報もJSONシリアライズ可能な形式で保存
                    result["original_entity"] = {
                        "entity_type": result["entity_type"],
                        "text": result["text"],
                        "score": result["confidence"],
                        "start": result["start"],
                        "end": result["end"],
                        "page_info": {"page_number": result["page"]},
                        "coordinates": result["coordinates"]
                    }
                    self.detection_results.append(result)
                
                logger.info(f"検出完了: {len(self.detection_results)}件")
                
            else:
                # フォールバック: 模擬データを使用
                logger.warning("Presidio processor利用不可、模擬データを使用")
                self.detection_results = [
                    {
                        "entity_type": "PERSON",
                        "text": "田中太郎",
                        "confidence": 0.85,
                        "page": 1,
                        "start": 0,
                        "end": 4,
                        "coordinates": {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
                    },
                    {
                        "entity_type": "PHONE_NUMBER", 
                        "text": "03-1234-5678",
                        "confidence": 0.92,
                        "page": 1,
                        "start": 10,
                        "end": 22,
                        "coordinates": {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
                    },
                    {
                        "entity_type": "LOCATION",
                        "text": "東京都渋谷区",
                        "confidence": 0.78,
                        "page": 1,
                        "start": 30,
                        "end": 36,
                        "coordinates": {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
                    }
                ]
            
            # 閾値フィルタリング
            filtered_results = []
            for result in self.detection_results:
                if result["confidence"] >= self.settings["threshold"]:
                    # エンティティタイプフィルタリング
                    if result["entity_type"] in self.settings["entities"]:
                        filtered_results.append(result)
            
            self.detection_results = filtered_results
            
            return {
                "success": True,
                "message": f"個人情報検出完了 ({len(self.detection_results)}件)",
                "results": self.detection_results,
                "count": len(self.detection_results)
            }
            
        except Exception as ex:
            logger.error(f"検出処理エラー: {ex}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"検出処理に失敗: {str(ex)}"
            }
    
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
    
    def generate_pdf_with_annotations(self) -> Dict:
        """現在の検出結果をアノテーション/ハイライトとしてPDFに適用し、ダウンロード用のパスを返す"""
        if not self.current_pdf_path or not self.pdf_document:
            return {
                "success": False,
                "message": "PDFファイルが利用できません"
            }
        
        try:
            logger.info(f"PDF保存用アノテーション適用開始: {self.current_pdf_path}")
            
            # アップロードフォルダの存在を確認
            upload_folder = app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder, exist_ok=True)
                logger.info(f"アップロードフォルダを作成: {upload_folder}")
            
            # 新しいPDFドキュメントを作成（元のPDFをコピー）
            temp_pdf_path = os.path.join(
                upload_folder, 
                f"annotated_{uuid.uuid4()}_{os.path.basename(self.current_pdf_path)}"
            )
            logger.info(f"生成予定ファイルパス: {temp_pdf_path}")
            
            # 新しいPDFドキュメントを作成
            new_doc = fitz.open()
            original_doc = fitz.open(self.current_pdf_path)
            
            # 元のPDFの各ページを新しいドキュメントにコピー
            for page_num in range(len(original_doc)):
                # ページをコピー
                new_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)
                new_page = new_doc[page_num]
                
                # 現在のページに対応する検出結果を取得
                page_entities = [
                    entity for entity in self.detection_results 
                    if entity.get('page', 1) == page_num + 1
                ]
                
                for entity in page_entities:
                    try:
                        # 座標情報がある場合は直接使用
                        if 'coordinates' in entity and entity['coordinates']:
                            coords = entity['coordinates']
                            if all(k in coords for k in ['x0', 'y0', 'x1', 'y1']) and any(coords[k] != 0 for k in coords):
                                rect = fitz.Rect(coords['x0'], coords['y0'], coords['x1'], coords['y1'])
                                logger.debug(f"座標使用: {entity['text']} at {rect}")
                            else:
                                # 座標情報が不完全な場合はテキスト検索
                                text_instances = new_page.search_for(entity['text'])
                                if not text_instances:
                                    continue
                                rect = text_instances[0]
                                logger.debug(f"テキスト検索: {entity['text']} at {rect}")
                        else:
                            # 座標情報がない場合はテキスト検索
                            text_instances = new_page.search_for(entity['text'])
                            if not text_instances:
                                continue
                            rect = text_instances[0]
                            logger.debug(f"テキスト検索(フォールバック): {entity['text']} at {rect}")
                        
                        # エンティティタイプに応じて色を設定
                        color_map = {
                            'PERSON': (1, 0.8, 0.8),      # 薄い赤
                            'LOCATION': (0.8, 1, 0.8),    # 薄い緑
                            'PHONE_NUMBER': (0.8, 0.8, 1), # 薄い青
                            'DATE_TIME': (1, 1, 0.8)      # 薄い黄
                        }
                        color = color_map.get(entity['entity_type'], (0.9, 0.9, 0.9))
                        
                        # マスキング方式に基づいてアノテーションを追加
                        masking_method = self.settings.get("masking_method", "highlight")
                        
                        if masking_method in ["highlight", "both"]:
                            # ハイライト注釈を追加
                            highlight = new_page.add_highlight_annot(rect)
                            highlight.set_colors(stroke=color)
                            highlight.set_info(title=f"個人情報: {self.get_entity_type_japanese(entity['entity_type'])}", 
                                             content=f"検出テキスト: {entity['text']}\n信頼度: {entity['confidence']:.2f}")
                            highlight.update()
                            logger.debug(f"ハイライト追加: {entity['text']}")
                        
                        if masking_method in ["annotation", "both"]:
                            # テキスト注釈を追加
                            annotation = new_page.add_text_annot(rect.tl, 
                                                           f"{self.get_entity_type_japanese(entity['entity_type'])}: {entity['text']}")
                            annotation.set_info(title="個人情報検出", 
                                               content=f"タイプ: {entity['entity_type']}\nテキスト: {entity['text']}\n信頼度: {entity['confidence']:.2f}")
                            annotation.update()
                            logger.debug(f"注釈追加: {entity['text']}")
                            
                    except Exception as e:
                        logger.warning(f"アノテーション追加失敗 for {entity['text']}: {e}")
            
            # 元のドキュメントを閉じる
            original_doc.close()
            
            # 新しいドキュメントを保存
            new_doc.save(temp_pdf_path)
            new_doc.close()
            
            # ファイルが正常に作成されたか確認
            if os.path.exists(temp_pdf_path):
                file_size = os.path.getsize(temp_pdf_path)
                logger.info(f"PDF保存用ファイル生成完了: {temp_pdf_path} (サイズ: {file_size} bytes)")
            else:
                logger.error(f"PDFファイル生成失敗: ファイルが作成されませんでした - {temp_pdf_path}")
                return {
                    "success": False,
                    "message": "PDFファイルの生成に失敗しました（ファイルが作成されませんでした）"
                }
            
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
    
    def get_entity_type_japanese(self, entity_type: str) -> str:
        """エンティティタイプの日本語名を返す"""
        mapping = {
            "PERSON": "人名",
            "LOCATION": "場所", 
            "PHONE_NUMBER": "電話番号",
            "DATE_TIME": "日時"
        }
        return mapping.get(entity_type, entity_type)
    
    def adjust_highlight_range(self, highlight_id: int, adjustment_type: str, amount: int = 1) -> Dict:
        """ハイライト範囲を調整"""
        try:
            if highlight_id >= len(self.detection_results):
                return {'success': False, 'message': '無効なハイライトIDです'}
            
            highlight = self.detection_results[highlight_id]
            original_text = highlight['text']
            page_num = highlight.get('page', 1) - 1  # 0-based index
            
            if not self.pdf_document or page_num >= len(self.pdf_document):
                return {'success': False, 'message': '無効なページ番号です'}
            
            page = self.pdf_document[page_num]
            page_text = page.get_text()
            
            # 現在のテキストの位置を特定
            text_start = page_text.find(original_text)
            if text_start == -1:
                return {'success': False, 'message': 'テキストが見つかりません'}
            
            text_end = text_start + len(original_text)
            
            # 範囲調整
            new_start = text_start
            new_end = text_end
            
            if adjustment_type == "extend_left" and text_start > 0:
                new_start = max(0, text_start - amount)
            elif adjustment_type == "extend_right" and text_end < len(page_text):
                new_end = min(len(page_text), text_end + amount)
            elif adjustment_type == "shrink_left" and text_end - text_start > amount:
                new_start = min(text_start + amount, text_end - 1)
            elif adjustment_type == "shrink_right" and text_end - text_start > amount:
                new_end = max(text_start + 1, text_end - amount)
            else:
                return {'success': False, 'message': f'調整できません: {adjustment_type}'}
            
            # 新しいテキスト
            new_text = page_text[new_start:new_end].strip()
            if not new_text:
                return {'success': False, 'message': '無効な範囲です'}
            
            # 新しい座標を計算
            text_instances = page.search_for(new_text)
            if not text_instances:
                return {'success': False, 'message': '新しいテキストの座標が見つかりません'}
            
            new_rect = text_instances[0]
            
            # ハイライト情報を更新
            highlight['text'] = new_text
            highlight['coordinates'] = {
                'x0': new_rect.x0,
                'y0': new_rect.y0,
                'x1': new_rect.x1,
                'y1': new_rect.y1
            }
            
            logger.info(f"ハイライト調整完了: '{original_text}' -> '{new_text}'")
            
            return {
                'success': True,
                'message': f'ハイライト範囲を調整しました: {adjustment_type}',
                'updated_highlight': highlight
            }
            
        except Exception as e:
            logger.error(f"ハイライト範囲調整エラー: {e}")
            return {'success': False, 'message': f'調整エラー: {str(e)}'}
    
    def find_highlight_at_position(self, page_num: int, x: float, y: float) -> Optional[Dict]:
        """指定座標のハイライトを検索"""
        try:
            page_based_1 = page_num + 1  # 1-based page number
            
            for i, entity in enumerate(self.detection_results):
                if entity.get('page', 1) != page_based_1:
                    continue
                
                # 座標情報をチェック
                coords = entity.get('coordinates')
                if coords and all(k in coords for k in ['x0', 'y0', 'x1', 'y1']):
                    # 座標内かチェック
                    if (coords['x0'] <= x <= coords['x1'] and 
                        coords['y0'] <= y <= coords['y1']):
                        # IDを追加
                        entity_copy = entity.copy()
                        entity_copy['id'] = i
                        return entity_copy
                else:
                    # 座標情報がない場合はテキスト検索で推定
                    if not self.pdf_document:
                        continue
                    
                    page = self.pdf_document[page_num]
                    text_instances = page.search_for(entity['text'])
                    
                    for rect in text_instances:
                        if rect.x0 <= x <= rect.x1 and rect.y0 <= y <= rect.y1:
                            # 座標を更新
                            entity_copy = entity.copy()
                            entity_copy['coordinates'] = {
                                'x0': rect.x0, 'y0': rect.y0,
                                'x1': rect.x1, 'y1': rect.y1
                            }
                            entity_copy['id'] = i
                            return entity_copy
            
            return None
            
        except Exception as e:
            logger.error(f"ハイライト検索エラー: {e}")
            return None


def allowed_file(filename):
    """アップロードされたファイルが許可されているかチェック"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_session_app() -> PresidioPDFWebApp:
    """現在のセッションのアプリケーションインスタンスを取得"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    if session_id not in sessions:
        sessions[session_id] = PresidioPDFWebApp(session_id)
    
    return sessions[session_id]


# Flask ルート定義
@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """PDFファイルアップロード"""
    try:
        if 'pdf_file' not in request.files:
            return jsonify({'success': False, 'message': 'ファイルが選択されていません'})
        
        file = request.files['pdf_file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'ファイルが選択されていません'})
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # ユニークなファイル名を生成
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # セッションアプリにPDFを読み込み
            app_instance = get_session_app()
            result = app_instance.load_pdf_file(file_path)
            
            if result['success']:
                return jsonify(result)
            else:
                # ファイルを削除
                try:
                    os.remove(file_path)
                except:
                    pass
                return jsonify(result)
        else:
            return jsonify({'success': False, 'message': '有効なPDFファイルを選択してください'})
    
    except Exception as e:
        logger.error(f"ファイルアップロードエラー: {e}")
        return jsonify({'success': False, 'message': f'アップロードエラー: {str(e)}'})


@app.route('/api/detect', methods=['POST'])
def detect_entities():
    """個人情報検出"""
    try:
        app_instance = get_session_app()
        if not app_instance.current_pdf_path:
            return jsonify({'success': False, 'message': 'PDFファイルが読み込まれていません'})
        
        result = app_instance.run_detection()
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"検出処理エラー: {e}")
        return jsonify({'success': False, 'message': f'検出エラー: {str(e)}'})


@app.route('/api/page/<int:page_num>')
def get_page_image(page_num):
    """PDFページ画像を取得（PDF.js統合版では不要だが互換性のため残す）"""
    try:
        # PDF.js版では直接クライアントでPDFを処理するため、
        # このエンドポイントは主に後方互換性のために残している
        return jsonify({
            'success': True,
            'message': 'PDF.js版では直接クライアントでPDFを処理します',
            'page': page_num
        })
    
    except Exception as e:
        logger.error(f"ページ画像取得エラー: {e}")
        return jsonify({'success': False, 'message': f'ページ取得エラー: {str(e)}'})


@app.route('/api/delete_entity/<int:index>', methods=['DELETE'])
def delete_entity(index):
    """エンティティ削除"""
    try:
        app_instance = get_session_app()
        result = app_instance.delete_entity(index)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"エンティティ削除エラー: {e}")
        return jsonify({'success': False, 'message': f'削除エラー: {str(e)}'})


@app.route('/api/generate_pdf', methods=['POST'])
def generate_pdf():
    """アノテーション付きPDFを生成"""
    try:
        app_instance = get_session_app()
        result = app_instance.generate_pdf_with_annotations()
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"PDF生成エラー: {e}")
        return jsonify({'success': False, 'message': f'生成エラー: {str(e)}'})


@app.route('/api/download_pdf/<path:filename>')
def download_pdf(filename):
    """生成されたPDFをダウンロード"""
    try:
        logger.info(f"PDFダウンロード要求: {filename}")
        
        # セキュリティチェック: アップロードフォルダ内のファイルのみ許可
        upload_folder = os.path.abspath(app.config['UPLOAD_FOLDER'])
        file_path = os.path.join(upload_folder, filename)
        file_path_abs = os.path.abspath(file_path)
        
        logger.info(f"ファイルパス確認: {file_path_abs}")
        logger.info(f"アップロードフォルダ: {upload_folder}")
        
        # パス検証
        if not file_path_abs.startswith(upload_folder):
            logger.error(f"セキュリティエラー: 許可されていないパス - {file_path_abs}")
            return jsonify({'success': False, 'message': 'ファイルアクセスが許可されていません'}), 403
        
        # ファイル存在確認
        if not os.path.exists(file_path_abs):
            logger.error(f"ファイルが見つかりません: {file_path_abs}")
            # アップロードフォルダ内のファイル一覧をログに出力（デバッグ用）
            try:
                files_in_upload = os.listdir(upload_folder)
                logger.info(f"アップロードフォルダ内のファイル: {files_in_upload}")
            except Exception as list_error:
                logger.error(f"フォルダ一覧取得エラー: {list_error}")
            return jsonify({'success': False, 'message': 'ファイルが見つかりません'}), 404
        
        # ファイルサイズ確認
        file_size = os.path.getsize(file_path_abs)
        logger.info(f"ダウンロード対象ファイル: {file_path_abs} (サイズ: {file_size} bytes)")
        
        # オリジナルファイル名を取得（アノテーション付きファイル名から復元）
        if filename.startswith('annotated_'):
            # annotated_{uuid}_{original_filename} の形式から元のファイル名を抽出
            parts = filename.split('_', 2)
            if len(parts) >= 3:
                original_name = parts[2]
                download_name = f"masked_{os.path.splitext(original_name)[0]}.pdf"
            else:
                download_name = f"masked_{filename}"
        else:
            download_name = filename
        
        logger.info(f"PDFダウンロード開始: {filename} as {download_name}")
        
        return send_file(
            file_path_abs,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/pdf'
        )
    
    except Exception as e:
        logger.error(f"PDFダウンロードエラー: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'ダウンロードエラー: {str(e)}'}), 500


@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """設定の取得・更新"""
    try:
        app_instance = get_session_app()
        
        if request.method == 'GET':
            return jsonify({
                'success': True,
                'settings': app_instance.settings
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            if 'entities' in data:
                app_instance.settings['entities'] = data['entities']
            if 'threshold' in data:
                app_instance.settings['threshold'] = float(data['threshold'])
            if 'masking_method' in data:
                app_instance.settings['masking_method'] = data['masking_method']
            
            return jsonify({
                'success': True,
                'message': '設定を更新しました',
                'settings': app_instance.settings
            })
    
    except Exception as e:
        logger.error(f"設定処理エラー: {e}")
        return jsonify({'success': False, 'message': f'設定エラー: {str(e)}'})


@app.route('/api/highlights/adjust', methods=['POST'])
def adjust_highlight():
    """ハイライト範囲を調整"""
    try:
        app_instance = get_session_app()
        
        if not app_instance.current_pdf_path or not app_instance.pdf_document:
            return jsonify({'success': False, 'message': 'PDFが読み込まれていません'})
        
        data = request.get_json()
        highlight_id = data.get('highlight_id')
        page_num = data.get('page_num', 0)
        adjustment_type = data.get('adjustment_type')  # 'extend_left', 'extend_right', 'shrink_left', 'shrink_right'
        amount = data.get('amount', 1)  # 調整する文字数
        
        # ハイライトを特定
        if highlight_id is None or highlight_id >= len(app_instance.detection_results):
            return jsonify({'success': False, 'message': '無効なハイライトIDです'})
        
        highlight = app_instance.detection_results[highlight_id]
        
        # ページ番号チェック
        if highlight.get('page', 1) != page_num + 1:
            return jsonify({'success': False, 'message': 'ページ番号が一致しません'})
        
        # 範囲調整処理
        result = app_instance.adjust_highlight_range(highlight_id, adjustment_type, amount)
        
        if result['success']:
            # ページ画像を再生成
            updated_image = app_instance.get_pdf_page_image(page_num, show_highlights=True)
            
            return jsonify({
                'success': True,
                'message': result['message'],
                'updated_highlight': result['updated_highlight'],
                'updated_image': updated_image
            })
        else:
            return jsonify({'success': False, 'message': result['message']})
    
    except Exception as e:
        logger.error(f"ハイライト調整エラー: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'ハイライト調整エラー: {str(e)}'})


@app.route('/api/highlights/adjust_batch', methods=['POST'])
def adjust_highlight_batch():
    """ハイライト範囲を一括調整"""
    try:
        app_instance = get_session_app()
        
        if not app_instance.current_pdf_path or not app_instance.pdf_document:
            return jsonify({'success': False, 'message': 'PDFが読み込まれていません'})
        
        data = request.get_json()
        highlight_id = data.get('highlight_id')
        page_num = data.get('page_num', 0)
        adjustments = data.get('adjustments', [])
        
        # ハイライトを特定
        if highlight_id is None or highlight_id >= len(app_instance.detection_results):
            return jsonify({'success': False, 'message': '無効なハイライトIDです'})
        
        highlight = app_instance.detection_results[highlight_id]
        
        # ページ番号チェック
        if highlight.get('page', 1) != page_num + 1:
            return jsonify({'success': False, 'message': 'ページ番号が一致しません'})
        
        logger.info(f"一括調整開始: {len(adjustments)}回の操作")
        
        # 調整を順次適用
        success_count = 0
        for adjustment in adjustments:
            adjustment_type = adjustment.get('type')
            result = app_instance.adjust_highlight_range(highlight_id, adjustment_type, 1)
            
            if result['success']:
                success_count += 1
                # ハイライト情報を更新
                highlight = result['updated_highlight']
                app_instance.detection_results[highlight_id] = highlight
            else:
                logger.warning(f"調整失敗: {adjustment_type} - {result['message']}")
                # 失敗した場合でも続行（部分的な成功を許可）
        
        if success_count > 0:
            # ページ画像を再生成
            updated_image = app_instance.get_pdf_page_image(page_num, show_highlights=True)
            
            return jsonify({
                'success': True,
                'message': f'{success_count}/{len(adjustments)}回の調整が完了しました',
                'updated_highlight': highlight,
                'updated_image': updated_image,
                'success_count': success_count,
                'total_count': len(adjustments)
            })
        else:
            return jsonify({'success': False, 'message': 'すべての調整が失敗しました'})
    
    except Exception as e:
        logger.error(f"一括ハイライト調整エラー: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'一括調整エラー: {str(e)}'})


@app.route('/api/highlights/add', methods=['POST'])
def add_highlight():
    """新しいハイライトを追加"""
    try:
        app_instance = get_session_app()
        
        if not app_instance.current_pdf_path:
            return jsonify({'success': False, 'message': 'PDFが読み込まれていません'})
        
        data = request.get_json()
        text = data.get('text', '').strip()
        entity_type = data.get('entity_type', 'CUSTOM')
        page_num = data.get('page', 1)
        coordinates = data.get('coordinates', {})
        
        if not text:
            return jsonify({'success': False, 'message': 'テキストが指定されていません'})
        
        # 新しいエンティティを作成
        new_entity = {
            'entity_type': entity_type,
            'text': text,
            'confidence': 1.0,
            'page': page_num,
            'start': 0,
            'end': len(text),
            'coordinates': coordinates
        }
        
        # 検出結果に追加
        app_instance.detection_results.append(new_entity)
        
        logger.info(f"新しいハイライトを追加: {text} (タイプ: {entity_type})")
        
        return jsonify({
            'success': True,
            'message': f'ハイライトを追加しました: {text}',
            'entity': new_entity,
            'total_count': len(app_instance.detection_results)
        })
    
    except Exception as e:
        logger.error(f"ハイライト追加エラー: {e}")
        return jsonify({'success': False, 'message': f'ハイライト追加エラー: {str(e)}'})

@app.route('/api/highlights/select', methods=['POST'])
def select_highlight():
    """座標からハイライトを選択（PDF.js版用に簡略化）"""
    try:
        app_instance = get_session_app()
        
        if not app_instance.current_pdf_path:
            return jsonify({'success': False, 'message': 'PDFが読み込まれていません'})
        
        data = request.get_json()
        page_num = data.get('page_num', 0)
        x = data.get('x')
        y = data.get('y')
        
        # 現在のページのエンティティから座標が近いものを検索
        page_entities = [
            (i, entity) for i, entity in enumerate(app_instance.detection_results)
            if entity.get('page', 1) == page_num + 1
        ]
        
        selected_index = -1
        min_distance = float('inf')
        
        for i, entity in page_entities:
            if 'coordinates' in entity and entity['coordinates']:
                coords = entity['coordinates']
                # 矩形の中心点との距離を計算
                center_x = (coords.get('x0', 0) + coords.get('x1', 0)) / 2
                center_y = (coords.get('y0', 0) + coords.get('y1', 0)) / 2
                distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                
                # 矩形内かつ最も近い点を選択
                if (coords.get('x0', 0) <= x <= coords.get('x1', 0) and
                    coords.get('y0', 0) <= y <= coords.get('y1', 0) and
                    distance < min_distance):
                    min_distance = distance
                    selected_index = i
        
        if selected_index >= 0:
            selected_entity = app_instance.detection_results[selected_index]
            selected_entity['id'] = selected_index
            return jsonify({
                'success': True,
                'highlight': selected_entity,
                'highlight_id': selected_index
            })
        else:
            return jsonify({
                'success': False,
                'message': 'この位置にはハイライトがありません'
            })
    
    except Exception as e:
        logger.error(f"ハイライト選択エラー: {e}")
        return jsonify({'success': False, 'message': f'ハイライト選択エラー: {str(e)}'})


if __name__ == '__main__':
    logger.info("Webアプリケーション開始")
    app.run(debug=True, host='0.0.0.0', port=5000)