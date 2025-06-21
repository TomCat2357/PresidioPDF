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
import shutil
import argparse
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

# ログフォルダを作成
LOG_FOLDER = 'log'
os.makedirs(LOG_FOLDER, exist_ok=True)

# ログ設定
log_filename = os.path.join(LOG_FOLDER, f"presidio_web_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO, # INFOレベルに変更して、本番運用でのログ量を調整
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# グローバル変数（セッション管理）
sessions = {}

# コマンドライン引数の解析
def parse_arguments():
    parser = argparse.ArgumentParser(description='PDF個人情報マスキングツール - Webアプリケーション版')
    parser.add_argument('--gpu', action='store_true', help='GPU（NVIDIA CUDA）を使用する（デフォルト: CPU使用）')
    parser.add_argument('--host', default='0.0.0.0', help='サーバーのホストアドレス（デフォルト: 0.0.0.0）')
    parser.add_argument('--port', type=int, default=5000, help='サーバーのポート番号（デフォルト: 5000）')
    parser.add_argument('--debug', action='store_true', help='デバッグモードで実行')
    return parser.parse_args()

# CPUモードの強制設定
def force_cpu_mode():
    """NVIDIA関連の環境変数を無効化してCPUモードを強制"""
    # CUDA関連の環境変数を無効化
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['NVIDIA_VISIBLE_DEVICES'] = ''
    
    # PyTorch関連
    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = ''
    
    # spaCy関連
    os.environ['SPACY_PREFER_GPU'] = '0'
    
    # Transformers関連
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_DATASETS_OFFLINE'] = '1'
    
    logger.info("CPUモードが強制的に有効化されました。GPU関連機能は無効です。")

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

    ### 修正箇所 ###
    # run_detectionメソッドを修正し、座標計算を確実に行うように変更
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
                        "line_rects": line_rects,  # 複数行矩形情報を追加
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
    
    def generate_pdf_with_annotations(self) -> Dict:
        """現在の検出結果をアノテーション/ハイライトとしてPDFに適用し、ダウンロード用のパスを返す"""
        if not self.current_pdf_path or not self.pdf_document:
            return {
                "success": False,
                "message": "PDFファイルが利用できません"
            }
        
        try:
            logger.info(f"PDF保存用アノテーション適用開始: {self.current_pdf_path}")
            
            upload_folder = app.config['UPLOAD_FOLDER']
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
                    annotation.set_info(title="個人情報検出", content=f"タイプ: {entity['entity_type']}\nテキスト: {entity['text']}")
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

def allowed_file(filename):
    """アップロードされたファイルが許可されているかチェック"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# グローバル変数でGPU使用フラグを管理
USE_GPU = False

def get_session_app() -> PresidioPDFWebApp:
    """現在のセッションのアプリケーションインスタンスを取得"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    if session_id not in sessions:
        sessions[session_id] = PresidioPDFWebApp(session_id, use_gpu=USE_GPU)
    
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
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            app_instance = get_session_app()
            result = app_instance.load_pdf_file(file_path)
            
            if result['success']:
                return jsonify(result)
            else:
                try:
                    os.remove(file_path)
                except OSError as e:
                    logger.warning(f"アップロード失敗後のファイル削除エラー: {e}")
                return jsonify(result)
        else:
            return jsonify({'success': False, 'message': '有効なPDFファイルを選択してください'})
    
    except Exception as e:
        logger.error(f"ファイルアップロードエラー: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'アップロードエラー: {str(e)}'})


@app.route('/api/detect', methods=['POST'])
def detect_entities():
    """個人情報検出"""
    try:
        app_instance = get_session_app()
        if not app_instance.current_pdf_path:
            return jsonify({'success': False, 'message': 'PDFファイルが読み込まれていません'})
        
        # クライアントから送信された設定を適用
        settings_data = request.get_json()
        if settings_data:
            app_instance.settings.update(settings_data)
            logger.info(f"セッションの設定を更新: {app_instance.settings}")

        result = app_instance.run_detection()
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"検出処理エラー: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'検出エラー: {str(e)}'})

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
        # クライアントからの最新のエンティティリストを受け取る
        data = request.get_json()
        if 'entities' in data:
            app_instance.detection_results = data['entities']
        result = app_instance.generate_pdf_with_annotations()
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"PDF生成エラー: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'生成エラー: {str(e)}'})


@app.route('/api/download_pdf/<path:filename>')
def download_pdf(filename):
    """生成されたPDFをダウンロード"""
    try:
        logger.info(f"PDFダウンロード要求: {filename}")
        
        upload_folder = os.path.abspath(app.config['UPLOAD_FOLDER'])
        file_path = os.path.join(upload_folder, filename)
        file_path_abs = os.path.abspath(file_path)
        
        if not file_path_abs.startswith(upload_folder):
            logger.error(f"セキュリティエラー: 許可されていないパス - {file_path_abs}")
            return jsonify({'success': False, 'message': 'ファイルアクセスが許可されていません'}), 403
        
        if not os.path.exists(file_path_abs):
            logger.error(f"ファイルが見つかりません: {file_path_abs}")
            return jsonify({'success': False, 'message': 'ファイルが見つかりません'}), 404
        
        if filename.startswith('annotated_'):
            parts = filename.split('_', 2)
            original_name = parts[2] if len(parts) >= 3 else filename
            download_name = f"masked_{os.path.splitext(original_name)[0]}.pdf"
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
            if 'masking_method' in data:
                app_instance.settings['masking_method'] = data['masking_method']
            
            logger.info(f"設定更新完了: {app_instance.settings}")
            return jsonify({
                'success': True,
                'message': '設定を更新しました',
                'settings': app_instance.settings
            })
    
    except Exception as e:
        logger.error(f"設定処理エラー: {e}")
        return jsonify({'success': False, 'message': f'設定エラー: {str(e)}'})

# このエンドポイントは手動調整機能が複雑なため、一旦コメントアウトします。
# 主な問題は座標の再計算と状態管理にあり、よりシンプルな解決策を優先しました。
# @app.route('/api/highlights/adjust', methods=['POST'])
# def adjust_highlight(): ...

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
        
        # フロントエンドから渡されたline_rectsを優先的に使用
        line_rects = data.get('line_rects', [])

        # line_rectsがフロントエンドから提供されない場合のフォールバック
        if not line_rects and hasattr(app_instance, 'processor') and app_instance.processor:
            try:
                pdf_doc = fitz.open(app_instance.current_pdf_path)
                page = pdf_doc[page_num - 1]
                # テキストの各行矩形を取得
                line_rects = app_instance.processor._get_text_line_rects(
                    page, text, 0, len(text)
                )
                pdf_doc.close()
            except Exception as e:
                logger.debug(f"複数行矩形取得エラー（フォールバック）: {e}")

        new_entity = {
            'entity_type': entity_type,
            'text': text,
            'page': page_num,
            'start': data.get('start', 0),
            'end': data.get('end', len(text)),
            'coordinates': coordinates,
            'line_rects': line_rects,  # 複数行矩形情報を追加
            'manual': True, # 手動追加フラグ
            'start_page': data.get('start_page', page_num),
            'end_page': data.get('end_page', page_num),
            'start_line': data.get('start_line', 0),
            'end_line': data.get('end_line', 0),
            'start_char': data.get('start_char', 0),
            'end_char': data.get('end_char', len(text))
        }
        
        # 手動追加の重複チェック
        if app_instance._is_duplicate_manual_addition(new_entity):
            return jsonify({
                'success': False, 
                'message': 'ほぼ同じ場所に同じタイプのハイライトが既に存在します'
            })
        
        app_instance.detection_results.append(new_entity)
        logger.info(f"新しいハイライトを手動追加: {text} (タイプ: {entity_type})")
        
        return jsonify({
            'success': True,
            'message': f'ハイライトを追加しました: {text}',
            'entity': new_entity,
            'total_count': len(app_instance.detection_results)
        })
    
    except Exception as e:
        logger.error(f"ハイライト追加エラー: {e}")
        return jsonify({'success': False, 'message': f'ハイライト追加エラー: {str(e)}'})


def main():
    """メイン実行関数"""
    global USE_GPU
    
    # コマンドライン引数の解析
    args = parse_arguments()
    
    # GPUフラグの設定
    USE_GPU = args.gpu
    
    # CPUモードの強制設定（--gpuが指定されていない場合）
    if not USE_GPU:
        force_cpu_mode()
        logger.info("CPUモードで起動します。GPU関連機能は無効化されました。")
    else:
        logger.info("GPUモードで起動します。NVIDIA CUDA機能が有効です。")
    
    logger.info("Webアプリケーション開始")
    logger.info(f"サーバー設定: {args.host}:{args.port}")
    logger.info(f"デバッグモード: {args.debug}")
    logger.info(f"処理モード: {'GPU' if USE_GPU else 'CPU'}")
    
    # Flaskアプリケーションの実行
    app.run(debug=args.debug, host=args.host, port=args.port)

if __name__ == '__main__':
    main()