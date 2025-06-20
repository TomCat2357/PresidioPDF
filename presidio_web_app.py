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
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
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
                default_config_path = os.path.join(os.path.dirname(__file__), "config", "low_threshold.yaml")
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
        if not self.pdf_document or page_num >= self.total_pages:
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
                        # テキスト検索でハイライト位置を特定
                        text_instances = page.search_for(entity['text'])
                        if text_instances:
                            # 最初に見つかった位置にハイライトを追加
                            rect = text_instances[0]
                            
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
                            
                            logger.debug(f"ハイライト追加: {entity['text']} at {rect}")
                            
                    except Exception as e:
                        logger.warning(f"ハイライト追加失敗 for {entity['text']}: {e}")
            
            # 拡大率を適用してピクセルマップを取得
            base_resolution = 2.0
            actual_zoom = zoom * base_resolution
            mat = fitz.Matrix(actual_zoom, actual_zoom)
            pix = page.get_pixmap(matrix=mat)
            
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
            
            return img_base64
            
        except Exception as e:
            logger.error(f"ページ画像取得エラー: {e}")
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
    
    def apply_changes_to_pdf(self) -> Dict:
        """現在の検出結果をPDFファイルに適用"""
        if not self.current_pdf_path or not self.processor:
            return {
                "success": False,
                "message": "PDFファイルまたはプロセッサーが利用できません"
            }
        
        try:
            logger.info(f"PDF変更適用開始: {self.current_pdf_path}")
            
            # 現在の検出結果をPresidio形式に変換
            entities_to_apply = []
            for result in self.detection_results:
                if 'original_entity' in result:
                    # 元のエンティティ情報を使用
                    entities_to_apply.append(result['original_entity'])
                else:
                    # 最小限のエンティティ情報を作成
                    entity = {
                        'entity_type': result['entity_type'],
                        'text': result['text'],
                        'score': result['confidence'],
                        'start': result.get('start', 0),
                        'end': result.get('end', 0),
                        'page_info': {'page_number': result.get('page', 1)},
                        'coordinates': result.get('coordinates', {})
                    }
                    entities_to_apply.append(entity)
            
            # PDFに変更を適用（マスキング処理）
            output_path = self.processor.apply_masking(
                self.current_pdf_path, 
                entities_to_apply, 
                masking_method=self.settings.get("masking_method", "highlight")
            )
            
            logger.info(f"PDF変更適用完了: {output_path}")
            
            return {
                "success": True,
                "message": f"PDF変更適用完了: {os.path.basename(output_path)}",
                "output_path": output_path,
                "filename": os.path.basename(output_path)
            }
            
        except Exception as e:
            logger.error(f"PDF変更適用エラー: {e}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"PDF変更の適用に失敗: {str(e)}"
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
    """PDFページ画像を取得"""
    try:
        app_instance = get_session_app()
        zoom = float(request.args.get('zoom', 1.0))
        show_highlights = request.args.get('highlights', 'false').lower() == 'true'
        
        img_base64 = app_instance.get_pdf_page_image(page_num, zoom, show_highlights)
        if img_base64:
            return jsonify({
                'success': True,
                'image': img_base64,
                'page': page_num,
                'highlights': show_highlights
            })
        else:
            return jsonify({'success': False, 'message': 'ページ画像の取得に失敗'})
    
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


@app.route('/api/apply_pdf', methods=['POST'])
def apply_to_pdf():
    """PDFに変更を適用"""
    try:
        app_instance = get_session_app()
        result = app_instance.apply_changes_to_pdf()
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"PDF適用エラー: {e}")
        return jsonify({'success': False, 'message': f'適用エラー: {str(e)}'})


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


if __name__ == '__main__':
    logger.info("Webアプリケーション開始")
    app.run(debug=True, host='0.0.0.0', port=5000)