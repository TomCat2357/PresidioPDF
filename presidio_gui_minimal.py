#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - 最小限版
"""

import FreeSimpleGUI as sg
import os
import json
import subprocess
import threading
import traceback
import sys
import logging
from datetime import datetime
from typing import List, Dict, Optional
import io
from PIL import Image
import fitz  # PyMuPDF

# 自プロジェクトのモジュールをインポート
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
try:
    from pdf_presidio_processor import PDFPresidioProcessor
    from config_manager import ConfigManager
    PRESIDIO_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Presidio processor import failed: {e}")
    PRESIDIO_AVAILABLE = False

# ログ設定
log_filename = f"presidio_gui_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PresidioPDFGUIMinimal:
    """PDF個人情報マスキングツールの最小限版"""
    
    def __init__(self):
        logger.info("アプリケーション開始")
        
        # アプリケーション状態
        self.current_pdf_path: Optional[str] = None
        self.detection_results: List[Dict] = []
        self.selected_index = -1
        
        # PDF表示関連
        self.pdf_document = None
        self.current_page = 0
        self.total_pages = 0
        self.page_images = []  # ページ画像のキャッシュ
        self.pdf_zoom = 1.0
        
        # 設定
        self.settings = {
            "entities": ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
            "threshold": 0.5
        }
        
        # デフォルトファイルパス
        self.default_config_path = os.path.join(os.path.dirname(__file__), "config", "low_threshold.yaml")
        self.default_pdf_path = os.path.join(os.path.dirname(__file__), "test_pdfs", "presen_00436_004.pdf")
        
        # Presidio プロセッサーの初期化
        self.processor = None
        self.config_file_path = None
        if PRESIDIO_AVAILABLE:
            try:
                # デフォルト設定ファイルを使用して初期化
                if os.path.exists(self.default_config_path):
                    config_manager = ConfigManager(config_file=self.default_config_path)
                    self.config_file_path = self.default_config_path
                    logger.info(f"デフォルト設定ファイル使用: {self.default_config_path}")
                else:
                    config_manager = ConfigManager()
                    logger.info("デフォルト設定で初期化")
                
                self.processor = PDFPresidioProcessor(config_manager)
                logger.info("Presidio processor初期化完了")
            except Exception as e:
                logger.error(f"Presidio processor初期化エラー: {e}")
                self.processor = None
        
        # GUI window
        self.window = None
        self._create_main_window()
        
        # デフォルトPDFファイルを読み込み
        self._load_default_files()
        
        logger.info("アプリケーション初期化完了")
    
    def _create_main_window(self):
        """メインウィンドウを作成"""
        
        # レイアウト
        # 左側パネル（コントロール）
        left_panel = [
            [sg.Text('PDF個人情報マスキングツール', font=('Arial', 14, 'bold'))],
            [sg.HSeparator()],
            
            # ファイル選択
            [sg.Text('PDFファイル:')],
            [sg.Input(key='-FILE_PATH-', size=(30, 1), readonly=True), 
             sg.Button('参照', key='-BROWSE-')],
            
            # 操作ボタン
            [sg.Button('検出開始', key='-DETECT-'),
             sg.Button('設定ファイル選択', key='-CONFIG_FILE-')],
            [sg.Button('設定', key='-SETTINGS-'),
             sg.Button('終了', key='-EXIT-')],
            
            [sg.HSeparator()],
            
            # PDF表示コントロール
            [sg.Text('PDFビューア:')],
            [sg.Text('ページ:', size=(8, 1)), sg.Text('0/0', key='-PAGE_INFO-', size=(10, 1))],
            [sg.Button('前ページ', key='-PREV_PAGE-', disabled=True),
             sg.Button('次ページ', key='-NEXT_PAGE-', disabled=True)],
            [sg.Text('拡大率:', size=(8, 1)), 
             sg.Slider(range=(25, 400), default_value=100, resolution=25, 
                      orientation='h', key='-ZOOM-', enable_events=True, size=(20, 15))],
            
            [sg.HSeparator()],
            
            # 検出結果
            [sg.Text('検出結果:')],
            [sg.Listbox(values=['初期化完了'], size=(35, 8), key='-RESULTS-', enable_events=True)],
            
            # プロパティ
            [sg.Text('選択されたエンティティ:')],
            [sg.Text('タイプ:'), sg.Text('-', key='-ENTITY_TYPE-', size=(15, 1))],
            [sg.Text('テキスト:'), sg.Text('-', key='-ENTITY_TEXT-', size=(25, 1))],
            [sg.Text('信頼度:'), sg.Text('-', key='-ENTITY_CONFIDENCE-', size=(10, 1))],
            [sg.Text('ページ:'), sg.Text('-', key='-ENTITY_PAGE-', size=(5, 1)),
             sg.Text('位置:'), sg.Text('-', key='-ENTITY_POSITION-', size=(15, 1))],
            [sg.Button('削除', key='-DELETE-', disabled=True),
             sg.Button('PDFに適用', key='-APPLY_TO_PDF-', disabled=True)],
            
            [sg.HSeparator()],
            [sg.Text('', key='-STATUS-', size=(40, 2))]
        ]
        
        # 右側パネル（PDFビューア）
        right_panel = [
            [sg.Text('PDF表示', font=('Arial', 12, 'bold'))],
            [sg.Image(key='-PDF_DISPLAY-', size=(600, 750), background_color='white')],
        ]
        
        # メインレイアウト
        layout = [
            [sg.Column(left_panel, vertical_alignment='top', size=(450, 750)), 
             sg.VSeparator(), 
             sg.Column(right_panel, vertical_alignment='top', size=(650, 750))]
        ]
        
        # ウィンドウ作成
        try:
            logger.info("ウィンドウ作成開始")
            self.window = sg.Window(
                'PDF個人情報マスキングツール',
                layout,
                size=(1150, 800),
                resizable=True,
                finalize=True
            )
            logger.info("ウィンドウ作成完了")
            
            # FreeSimpleGUIのListbox初期テスト
            try:
                logger.info("FreeSimpleGUI Listbox初期テスト開始")
                test_list = ["検出待機中..."]
                
                try:
                    self.window['-RESULTS-'].update(values=test_list)
                    logger.info("初期Listbox更新成功")
                except Exception as e1:
                    logger.error(f"初期Listbox更新失敗: {e1}")
                    
                logger.info("FreeSimpleGUI Listbox初期テスト完了")
            except Exception as test_e:
                logger.error(f"FreeSimpleGUI Listbox初期テストエラー: {test_e}")
                
        except Exception as e:
            logger.error(f"ウィンドウ作成エラー: {e}")
            logger.error(traceback.format_exc())
            raise
        
        # 初期状態の設定
        self._update_status("準備完了 - PDFファイルを選択するか、検出開始ボタンを押してください")
    
    def _load_default_files(self):
        """デフォルトファイルを読み込み"""
        try:
            # デフォルトPDFファイルが存在する場合は読み込み
            if os.path.exists(self.default_pdf_path):
                logger.info(f"デフォルトPDFファイル読み込み: {self.default_pdf_path}")
                self.window['-FILE_PATH-'].update(self.default_pdf_path)
                self._load_pdf_file(self.default_pdf_path)
                self._update_status(f"デフォルトPDFファイル読み込み完了: {os.path.basename(self.default_pdf_path)}")
            else:
                logger.warning(f"デフォルトPDFファイルが見つかりません: {self.default_pdf_path}")
                self._update_status("デフォルトPDFファイルが見つかりません - 手動でファイルを選択してください")
                
        except Exception as e:
            logger.error(f"デフォルトファイル読み込みエラー: {e}")
            self._update_status("デフォルトファイル読み込みエラー - 手動でファイルを選択してください")
    
    def _update_status(self, message: str):
        """ステータスを更新"""
        if self.window:
            self.window['-STATUS-'].update(message)
    
    def _load_pdf_file(self, file_path: str):
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
            self.current_page = 0
            self.page_images = []  # キャッシュクリア
            
            # ページ情報更新
            self._update_page_info()
            
            # 最初のページを表示
            self._display_current_page()
            
            # ナビゲーションボタンの状態更新
            self._update_navigation_buttons()
            
            # ファイル名表示
            filename = os.path.basename(file_path)
            self._update_status(f"PDFファイル読み込み完了: {filename} ({self.total_pages}ページ)")
            
            logger.info(f"PDFファイル読み込み完了: {self.total_pages}ページ")
            
        except Exception as ex:
            logger.error(f"PDFファイル読み込みエラー: {ex}")
            sg.popup_error(f"PDFファイルの読み込みに失敗しました:\n{str(ex)}")
    
    def _browse_file(self):
        """ファイル選択ダイアログを開く"""
        try:
            logger.info("参照ボタンが押されました")
            file_path = sg.popup_get_file(
                'PDFファイルを選択してください',
                file_types=(("PDF Files", "*.pdf"),),
                title="PDFファイル選択"
            )
            
            logger.info(f"ファイル選択結果: {file_path}")
            
            if file_path and os.path.isfile(file_path) and file_path.lower().endswith('.pdf'):
                logger.info(f"有効なPDFファイルを選択: {file_path}")
                self.window['-FILE_PATH-'].update(file_path)
                self._load_pdf_file(file_path)
                logger.info(f"ファイル選択完了: {file_path}")
            elif file_path:
                logger.warning(f"無効なファイル: {file_path}")
                sg.popup_error("有効なPDFファイルを選択してください")
            else:
                logger.info("ファイル選択がキャンセルされました")
                
        except Exception as e:
            logger.error(f"ファイル選択エラー: {e}")
            logger.error(traceback.format_exc())
            sg.popup_error(f"ファイル選択でエラーが発生しました:\n{str(e)}")
    
    def _start_detection(self):
        """個人情報検出を開始"""
        # PDFファイルが選択されていない場合はファイル選択を促す
        if not self.current_pdf_path:
            sg.popup_ok("PDFファイルを選択してから検出を開始してください", title="ファイル選択が必要")
            
            # ファイル選択ダイアログを開く
            file_path = sg.popup_get_file(
                "PDFファイルを選択してください",
                file_types=(("PDF Files", "*.pdf"), ("All Files", "*.*")),
                initial_folder=os.path.expanduser("~")
            )
            
            if file_path and os.path.isfile(file_path) and file_path.lower().endswith('.pdf'):
                self._load_pdf_file(file_path)
                self.window['-FILE_PATH-'].update(file_path)
            else:
                self._update_status("PDFファイルが選択されませんでした")
                return
        
        self._update_status("個人情報検出中...")
        
        # 同期的に検出処理を実行
        self._run_detection()
    
    def _run_detection(self):
        """個人情報検出処理を実行"""
        try:
            logger.info(f"個人情報検出開始: {self.current_pdf_path}")
            
            if self.processor and PRESIDIO_AVAILABLE:
                # 実際のPresidio処理を実行
                logger.info("Presidio processorを使用して検出を実行")
                entities = self.processor.analyze_pdf(self.current_pdf_path)
                
                # 結果を変換
                self.detection_results = []
                for entity in entities:
                    result = {
                        "entity_type": entity.get("entity_type", "UNKNOWN"),
                        "text": entity.get("text", ""),
                        "confidence": entity.get("score", 0.0),
                        "page": entity.get("page_info", {}).get("page_number", 1),
                        "start": entity.get("start", 0),
                        "end": entity.get("end", 0),
                        "coordinates": entity.get("coordinates", {}),
                        "original_entity": entity  # 元のエンティティ情報を保持
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
                        "end": 4
                    },
                    {
                        "entity_type": "PHONE_NUMBER", 
                        "text": "03-1234-5678",
                        "confidence": 0.92,
                        "page": 1,
                        "start": 10,
                        "end": 22
                    },
                    {
                        "entity_type": "LOCATION",
                        "text": "東京都渋谷区",
                        "confidence": 0.78,
                        "page": 1,
                        "start": 30,
                        "end": 36
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
            
            # 直接UI更新
            self._update_results_list()
            self._update_status(f"個人情報検出完了 ({len(self.detection_results)}件)")
            
            # PDFに適用ボタンを有効化
            if len(self.detection_results) > 0:
                self.window['-APPLY_TO_PDF-'].update(disabled=False)
                
        except Exception as ex:
            logger.error(f"検出処理エラー: {ex}")
            logger.error(traceback.format_exc())
            sg.popup_error(f"検出処理に失敗しました:\n{str(ex)}")
            self._update_status("検出処理エラー")
    
    def _update_results_list(self):
        """検出結果一覧を更新"""
        results_display = []
        
        logger.info(f"検出結果一覧更新開始: {len(self.detection_results)}件")
        
        # まずテスト用のデータで試す
        test_data = ["テスト1: 田中太郎", "テスト2: 03-1234-5678", "テスト3: 東京都"]
        
        for i, result in enumerate(self.detection_results):
            entity_type_jp = self._get_entity_type_japanese(result["entity_type"])
            display_text = f"{entity_type_jp}: {result['text']} (信頼度: {result['confidence']:.2f})"
            results_display.append(display_text)
            if i < 5:  # 最初の5件をログに出力
                logger.debug(f"結果{i+1}: {display_text}")
        
        logger.info(f"リストボックス更新: {len(results_display)}項目")
        
        # FreeSimpleGUIのListboxに検出結果を表示
        logger.info("FreeSimpleGUIのListboxに検出結果を表示")
        try:
            # 結果をリスト形式で表示
            if not results_display:
                display_list = ["検出結果がありません"]
            else:
                # 番号付きで表示
                display_list = []
                for i, display_text in enumerate(results_display, 1):
                    display_list.append(f"{i:2d}. {display_text}")
            
            # FreeSimpleGUIのListbox更新
            try:
                self.window['-RESULTS-'].update(values=display_list)
                logger.info("Listbox更新成功")
            except Exception as e1:
                logger.error(f"Listbox更新失敗: {e1}")
                logger.error(traceback.format_exc())
            
            logger.info(f"検出結果表示完了: {len(results_display)}項目")
            
        except Exception as e:
            logger.error(f"検出結果表示エラー: {e}")
            logger.error(traceback.format_exc())
        
        logger.info("リストボックス更新完了")
    
    def _get_entity_type_japanese(self, entity_type: str) -> str:
        """エンティティタイプの日本語名を返す"""
        mapping = {
            "PERSON": "人名",
            "LOCATION": "場所", 
            "PHONE_NUMBER": "電話番号",
            "DATE_TIME": "日時"
        }
        return mapping.get(entity_type, entity_type)
    
    def _select_entity(self, index: int):
        """エンティティを選択"""
        try:
            if 0 <= index < len(self.detection_results):
                self.selected_index = index
                entity = self.detection_results[index]
                
                # プロパティ更新
                entity_type_jp = self._get_entity_type_japanese(entity["entity_type"])
                self.window['-ENTITY_TYPE-'].update(entity_type_jp)
                self.window['-ENTITY_TEXT-'].update(entity["text"])
                self.window['-ENTITY_CONFIDENCE-'].update(f"{entity['confidence']:.3f}")
                self.window['-ENTITY_PAGE-'].update(str(entity.get("page", 1)))
                
                # 位置情報
                start = entity.get("start", 0)
                end = entity.get("end", 0)
                position_text = f"{start}-{end}" if start != end else str(start)
                self.window['-ENTITY_POSITION-'].update(position_text)
                
                self.window['-DELETE-'].update(disabled=False)
                
                # 該当ページに移動
                entity_page = entity.get('page', 1) - 1  # 0ベースに変換
                if self.pdf_document and 0 <= entity_page < self.total_pages:
                    if entity_page != self.current_page:
                        self._go_to_page(entity_page)
                
                logger.info(f"エンティティ選択: {entity_type_jp} '{entity['text']}' at page {entity.get('page', 1)}")
                
        except Exception as e:
            logger.error(f"Error in _select_entity: {e}")
            print(f"Error in _select_entity: {e}")  # デバッグ用
    
    def _delete_annotation(self):
        """選択されたアノテーションを削除"""
        if self.selected_index >= 0:
            entity = self.detection_results[self.selected_index]
            
            # 削除確認ダイアログ
            choice = sg.popup_yes_no(
                f"検出結果「{entity['text']}」({self._get_entity_type_japanese(entity['entity_type'])})を削除しますか？",
                title="削除確認"
            )
            
            if choice == "Yes":
                # 検出結果から削除
                deleted_entity = self.detection_results.pop(self.selected_index)
                
                # UI更新
                self._update_results_list()
                self._clear_properties()
                
                logger.info(f"エンティティ削除: {deleted_entity['text']} (タイプ: {deleted_entity['entity_type']})")
                self._update_status(f"削除完了: {deleted_entity['text']}")
                
                # PDFの表示を更新（ハイライトの削除を反映）
                self._display_current_page()
    
    def _apply_changes_to_pdf(self):
        """現在の検出結果をPDFファイルに適用"""
        if not self.current_pdf_path or not self.processor:
            sg.popup_error("PDFファイルまたはプロセッサーが利用できません")
            return
        
        try:
            self._update_status("PDFファイルに変更を適用中...")
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
                masking_method="annotation"
            )
            
            logger.info(f"PDF変更適用完了: {output_path}")
            
            # 適用されたPDFファイルを表示中のPDFとして読み込み直す
            choice = sg.popup_yes_no(
                f"PDFファイルに変更が適用されました:\n{os.path.basename(output_path)}\n\n"
                "適用されたPDFファイルを表示しますか？",
                title="PDF適用完了"
            )
            
            if choice == "Yes":
                self._reload_applied_pdf(output_path)
            
            self._update_status(f"PDF変更適用完了: {os.path.basename(output_path)}")
            
        except Exception as e:
            logger.error(f"PDF変更適用エラー: {e}")
            logger.error(traceback.format_exc())
            sg.popup_error(f"PDF変更の適用に失敗しました:\n{str(e)}")
            self._update_status("PDF変更適用エラー")
    
    def _update_page_info(self):
        """ページ情報を更新"""
        if self.pdf_document:
            page_text = f"{self.current_page + 1}/{self.total_pages}"
            self.window['-PAGE_INFO-'].update(page_text)
    
    def _update_navigation_buttons(self):
        """ナビゲーションボタンの状態を更新"""
        if self.pdf_document:
            self.window['-PREV_PAGE-'].update(disabled=(self.current_page <= 0))
            self.window['-NEXT_PAGE-'].update(disabled=(self.current_page >= self.total_pages - 1))
        else:
            self.window['-PREV_PAGE-'].update(disabled=True)
            self.window['-NEXT_PAGE-'].update(disabled=True)
    
    def _display_current_page(self):
        """現在のページを表示"""
        if not self.pdf_document or self.current_page >= self.total_pages:
            return
        
        try:
            # ページを取得
            page = self.pdf_document[self.current_page]
            
            # より大きなベース解像度を設定（高DPI対応）
            base_resolution = 2.0  # 基本解像度を2倍に
            actual_zoom = self.pdf_zoom * base_resolution
            
            # 拡大率を適用してピクセルマップを取得
            mat = fitz.Matrix(actual_zoom, actual_zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # PIL Imageに変換
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # 表示サイズに調整（最大600x750で高解像度表示）
            display_size = (600, 750)
            img.thumbnail(display_size, Image.Resampling.LANCZOS)
            
            # バイト配列に変換してGUIに表示
            bio = io.BytesIO()
            img.save(bio, format='PNG')
            self.window['-PDF_DISPLAY-'].update(data=bio.getvalue())
            
            # ハイライトを描画（検出結果がある場合）
            if self.detection_results:
                self._draw_highlights_on_page()
            
        except Exception as e:
            logger.error(f"ページ表示エラー: {e}")
            logger.error(traceback.format_exc())
    
    def _draw_highlights_on_page(self):
        """現在ページにハイライトを描画"""
        if not self.pdf_document or not self.detection_results:
            return
        
        try:
            # 現在のページに対応する検出結果を取得
            page_entities = [
                entity for entity in self.detection_results 
                if entity.get('page', 1) == self.current_page + 1
            ]
            
            if not page_entities:
                return
            
            # ページを取得
            page = self.pdf_document[self.current_page]
            
            # より大きなベース解像度を設定
            base_resolution = 2.0
            actual_zoom = self.pdf_zoom * base_resolution
            
            # 一時的にハイライト用の注釈を追加
            temp_annotations = []
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
            mat = fitz.Matrix(actual_zoom, actual_zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # PIL Imageに変換
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # 表示サイズに調整
            display_size = (600, 750)
            img.thumbnail(display_size, Image.Resampling.LANCZOS)
            
            # バイト配列に変換してGUIに表示
            bio = io.BytesIO()
            img.save(bio, format='PNG')
            self.window['-PDF_DISPLAY-'].update(data=bio.getvalue())
            
            # 一時的な注釈を削除（表示用のみ）
            for annot in temp_annotations:
                page.delete_annot(annot)
            
            logger.info(f"ページ {self.current_page + 1} に {len(page_entities)} 件のハイライトを描画完了")
            
        except Exception as e:
            logger.error(f"ハイライト描画エラー: {e}")
            logger.error(traceback.format_exc())
    
    def _go_to_page(self, page_num: int):
        """指定ページに移動"""
        if self.pdf_document and 0 <= page_num < self.total_pages:
            self.current_page = page_num
            self._update_page_info()
            self._display_current_page()
            self._update_navigation_buttons()
    
    def _reload_applied_pdf(self, new_pdf_path: str):
        """適用されたPDFファイルを読み込み直す"""
        try:
            logger.info(f"適用されたPDFファイルをリロード: {new_pdf_path}")
            
            # 現在のPDFドキュメントを閉じる
            if self.pdf_document:
                self.pdf_document.close()
            
            # 新しいPDFファイルを開く
            self.pdf_document = fitz.open(new_pdf_path)
            self.current_pdf_path = new_pdf_path
            self.total_pages = len(self.pdf_document)
            self.page_images = []  # キャッシュクリア
            
            # ファイルパス表示を更新
            self.window['-FILE_PATH-'].update(new_pdf_path)
            
            # ページ情報更新
            self._update_page_info()
            
            # 現在のページを再表示（物理的な注釈が反映される）
            self._display_current_page()
            
            # ナビゲーションボタンの状態更新
            self._update_navigation_buttons()
            
            logger.info(f"PDFリロード完了: {os.path.basename(new_pdf_path)}")
            
        except Exception as e:
            logger.error(f"PDFリロードエラー: {e}")
            logger.error(traceback.format_exc())
            sg.popup_error(f"PDFファイルのリロードに失敗しました:\n{str(e)}")
    
    def _clear_properties(self):
        """プロパティをクリア"""
        self.window['-ENTITY_TYPE-'].update("-")
        self.window['-ENTITY_TEXT-'].update("-")
        self.window['-ENTITY_CONFIDENCE-'].update("-")
        self.window['-ENTITY_PAGE-'].update("-")
        self.window['-ENTITY_POSITION-'].update("-")
        self.window['-DELETE-'].update(disabled=True)
        
        # PDFに適用ボタンの状態を検出結果数に応じて設定
        has_results = len(self.detection_results) > 0
        self.window['-APPLY_TO_PDF-'].update(disabled=not has_results)
        
        self.selected_index = -1
    
    def _select_config_file(self):
        """設定ファイルを選択"""
        file_path = sg.popup_get_file(
            '設定ファイルを選択してください',
            file_types=(("YAML Files", "*.yaml"), ("All Files", "*.*")),
            initial_folder=os.path.join(os.path.dirname(__file__), "config")
        )
        
        if file_path and os.path.isfile(file_path):
            try:
                # 新しい設定ファイルでプロセッサーを再初期化
                config_manager = ConfigManager(config_file=file_path)
                self.processor = PDFPresidioProcessor(config_manager)
                self.config_file_path = file_path
                
                sg.popup(f'設定ファイルが読み込まれました:\n{os.path.basename(file_path)}')
                logger.info(f"設定ファイル選択: {file_path}")
                
            except Exception as e:
                logger.error(f"設定ファイル読み込みエラー: {e}")
                sg.popup_error(f'設定ファイルの読み込みに失敗しました:\n{str(e)}')
    
    def _open_settings(self):
        """設定ダイアログを開く"""
        current_config_display = self.config_file_path or 'デフォルト設定'
        if self.config_file_path:
            current_config_display = os.path.basename(self.config_file_path)
            
        layout = [
            [sg.Text('現在の設定ファイル:')],
            [sg.Text(current_config_display, key='-CONFIG_PATH-')],
            [sg.Text('検出対象エンティティ')],
            [sg.Checkbox('人名', key='-PERSON-', default='PERSON' in self.settings['entities'])],
            [sg.Checkbox('場所', key='-LOCATION-', default='LOCATION' in self.settings['entities'])],
            [sg.Checkbox('電話番号', key='-PHONE-', default='PHONE_NUMBER' in self.settings['entities'])],
            [sg.Checkbox('日時', key='-DATE-', default='DATE_TIME' in self.settings['entities'])],
            [sg.Text('信頼度閾値')],
            [sg.Slider(range=(0.0, 1.0), default_value=self.settings['threshold'], 
                      resolution=0.1, orientation='h', key='-THRESHOLD-')],
            [sg.Button('保存'), sg.Button('キャンセル')]
        ]
        
        window = sg.Window('設定', layout, modal=True)
        
        while True:
            event, values = window.read()
            
            if event in (sg.WIN_CLOSED, 'キャンセル'):
                break
            elif event == '保存':
                # 設定を保存
                entities = []
                if values['-PERSON-']:
                    entities.append('PERSON')
                if values['-LOCATION-']:
                    entities.append('LOCATION')
                if values['-PHONE-']:
                    entities.append('PHONE_NUMBER')
                if values['-DATE-']:
                    entities.append('DATE_TIME')
                
                self.settings['entities'] = entities
                self.settings['threshold'] = values['-THRESHOLD-']
                
                sg.popup('設定が保存されました')
                break
        
        window.close()
    
    def run(self):
        """メインイベントループ"""
        while True:
            try:
                event, values = self.window.read()
                
                if event in (sg.WIN_CLOSED, '-EXIT-'):
                    break
                
                # ファイル選択の処理 - ファイルパスが変更された場合のみ
                if values and '-FILE_PATH-' in values and values['-FILE_PATH-']:
                    current_file = values['-FILE_PATH-']
                    if (current_file != self.current_pdf_path and 
                        os.path.isfile(current_file) and 
                        current_file.lower().endswith('.pdf')):
                        self._load_pdf_file(current_file)
                
                # イベント処理
                if event == '-BROWSE-':
                    self._browse_file()
                elif event == '-DETECT-':
                    self._start_detection()
                elif event == '-SETTINGS-':
                    self._open_settings()
                elif event == '-CONFIG_FILE-':
                    self._select_config_file()
                elif event == '-RESULTS-':
                    if values and '-RESULTS-' in values and values['-RESULTS-']:
                        try:
                            logger.debug(f"Results selection event: {values['-RESULTS-']}")
                            # 選択されたアイテムのインデックスを取得
                            selected_items = values['-RESULTS-']
                            if isinstance(selected_items, list) and len(selected_items) > 0:
                                # リストボックスから全ての値を取得
                                all_items = []
                                for result in self.detection_results:
                                    entity_type_jp = self._get_entity_type_japanese(result["entity_type"])
                                    display_text = f"{entity_type_jp}: {result['text']} (信頼度: {result['confidence']:.2f})"
                                    all_items.append(display_text)
                                
                                # 選択されたアイテムのインデックスを探す
                                selected_text = selected_items[0]
                                if selected_text in all_items:
                                    selected_index = all_items.index(selected_text)
                                    logger.info(f"エンティティ選択: index={selected_index}, text={selected_text}")
                                    self._select_entity(selected_index)
                        except (ValueError, IndexError, AttributeError) as e:
                            logger.error(f"リスト選択エラー: {e}")
                            logger.error(traceback.format_exc())
                elif event == '-DELETE-':
                    self._delete_annotation()
                elif event == '-APPLY_TO_PDF-':
                    self._apply_changes_to_pdf()
                elif event == '-PREV_PAGE-':
                    if self.current_page > 0:
                        self._go_to_page(self.current_page - 1)
                elif event == '-NEXT_PAGE-':
                    if self.current_page < self.total_pages - 1:
                        self._go_to_page(self.current_page + 1)
                elif event == '-ZOOM-':
                    if values and '-ZOOM-' in values:
                        new_zoom_percent = values['-ZOOM-']
                        new_zoom = new_zoom_percent / 100.0  # パーセントから倍率に変換
                        if abs(new_zoom - self.pdf_zoom) > 0.05:  # 変化があった場合のみ更新
                            self.pdf_zoom = new_zoom
                            self._display_current_page()
                    
            except Exception as e:
                logger.error(f"メインループでエラー: {e}")
                logger.error(f"Event: {event}")
                logger.error(f"Values: {values}")
                logger.error(traceback.format_exc())
                # エラーダイアログ表示
                sg.popup_error(f"エラーが発生しました:\n{e}\n\nログファイル: {log_filename}")
        
        logger.info("アプリケーション終了")
        
        # PDFドキュメントをクローズ
        if self.pdf_document:
            self.pdf_document.close()
        
        self.window.close()


def main():
    """メイン関数"""
    try:
        logger.info("メイン関数開始")
        app = PresidioPDFGUIMinimal()
        logger.info("GUIアプリケーション作成完了")
        app.run()
        logger.info("GUIアプリケーション実行完了")
    except Exception as e:
        logger.error(f"メイン関数でエラー: {e}")
        logger.error(traceback.format_exc())
        try:
            sg.popup_error(f"エラーが発生しました:\n{str(e)}")
        except:
            print(f"エラーが発生しました: {str(e)}")
            print(traceback.format_exc())


if __name__ == "__main__":
    main()