#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - 最小限版
"""

import TkEasyGUI as sg
import os
import json
import subprocess
import threading
import traceback
import sys
import logging
from datetime import datetime
from typing import List, Dict, Optional

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
        
        # 設定
        self.settings = {
            "entities": ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
            "threshold": 0.5
        }
        
        # Presidio プロセッサーの初期化
        self.processor = None
        self.config_file_path = None
        if PRESIDIO_AVAILABLE:
            try:
                # デフォルト設定で初期化（後で設定ファイルを選択可能）
                config_manager = ConfigManager()
                self.processor = PDFPresidioProcessor(config_manager)
                logger.info("Presidio processor初期化完了")
            except Exception as e:
                logger.error(f"Presidio processor初期化エラー: {e}")
                self.processor = None
        
        # GUI window
        self.window = None
        self._create_main_window()
        logger.info("アプリケーション初期化完了")
    
    def _create_main_window(self):
        """メインウィンドウを作成"""
        
        # レイアウト
        layout = [
            [sg.Text('PDF個人情報マスキングツール', font=('Arial', 16, 'bold'))],
            [sg.HSeparator()],
            
            # ファイル選択
            [sg.Text('PDFファイル:'), 
             sg.Input(key='-FILE_PATH-', size=(50, 1), readonly=True),
             sg.FileBrowse('参照', file_types=(("PDF Files", "*.pdf"),))],
            
            # ボタン
            [sg.Button('検出開始', key='-DETECT-'),
             sg.Button('設定', key='-SETTINGS-'),
             sg.Button('設定ファイル選択', key='-CONFIG_FILE-'),
             sg.Button('終了', key='-EXIT-')],
            
            [sg.HSeparator()],
            
            # 検出結果
            [sg.Text('検出結果:')],
            [sg.Listbox(values=[], size=(80, 15), key='-RESULTS-', enable_events=True)],
            
            # プロパティ
            [sg.Text('選択されたエンティティ:')],
            [sg.Text('タイプ:'), sg.Text('-', key='-ENTITY_TYPE-', size=(15, 1)),
             sg.Text('テキスト:'), sg.Text('-', key='-ENTITY_TEXT-', size=(20, 1))],
            [sg.Text('信頼度:'), sg.Text('-', key='-ENTITY_CONFIDENCE-', size=(10, 1)),
             sg.Text('ページ:'), sg.Text('-', key='-ENTITY_PAGE-', size=(5, 1)),
             sg.Text('位置:'), sg.Text('-', key='-ENTITY_POSITION-', size=(15, 1))],
            [sg.Button('削除', key='-DELETE-', disabled=True),
             sg.Button('PDFに適用', key='-APPLY_TO_PDF-', disabled=True)],
            
            [sg.HSeparator()],
            [sg.Text('', key='-STATUS-', size=(80, 1))]
        ]
        
        # ウィンドウ作成
        self.window = sg.Window(
            'PDF個人情報マスキングツール',
            layout,
            size=(900, 600),
            resizable=True
        )
        
        # 初期状態の設定
        self._update_status("準備完了 - PDFファイルを選択するか、検出開始ボタンを押してください")
    
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
            
            # ファイル名表示
            filename = os.path.basename(file_path)
            self._update_status(f"PDFファイル読み込み完了: {filename}")
            
            logger.info("PDFファイル読み込み完了")
            
        except Exception as ex:
            logger.error(f"PDFファイル読み込みエラー: {ex}")
            sg.popup_error(f"PDFファイルの読み込みに失敗しました:\n{str(ex)}")
    
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
        
        for result in self.detection_results:
            entity_type_jp = self._get_entity_type_japanese(result["entity_type"])
            display_text = f"{entity_type_jp}: {result['text']} (信頼度: {result['confidence']:.2f})"
            results_display.append(display_text)
        
        self.window['-RESULTS-'].update(values=results_display)
    
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
                
                logger.info(f"エンティティ選択: {entity_type_jp} '{entity['text']}' at page {entity.get('page', 1)}")
                
        except Exception as e:
            logger.error(f"Error in _select_entity: {e}")
            print(f"Error in _select_entity: {e}")  # デバッグ用
    
    def _delete_annotation(self):
        """選択されたアノテーションを削除"""
        if self.selected_index >= 0:
            entity = self.detection_results[self.selected_index]
            
            # 削除確認ダイアログを詳細化
            choice = sg.popup_yes_no(
                f"「{entity['text']}」を削除しますか？\n\n"
                f"リストから削除: 検出結果リストからのみ削除\n"
                f"PDFから削除: 実際のPDFファイルに変更を適用",
                title="削除確認"
            )
            
            if choice == "Yes":
                # 検出結果から削除
                del self.detection_results[self.selected_index]
                
                # UI更新
                self._update_results_list()
                self._clear_properties()
                
                logger.info(f"エンティティ削除: {entity['text']} (タイプ: {entity['entity_type']})")
                
                # PDFファイルに変更を適用するかユーザーに確認
                apply_to_pdf = sg.popup_yes_no(
                    "PDFファイルにも変更を適用しますか？\n"
                    "（実際のPDFファイルからハイライト/注釈を削除）",
                    title="PDF適用確認"
                )
                
                if apply_to_pdf == "Yes":
                    self._apply_changes_to_pdf()
    
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
            self._update_status(f"PDF変更適用完了: {os.path.basename(output_path)}")
            
            sg.popup(f"PDFファイルに変更が適用されました:\n{os.path.basename(output_path)}")
            
        except Exception as e:
            logger.error(f"PDF変更適用エラー: {e}")
            logger.error(traceback.format_exc())
            sg.popup_error(f"PDF変更の適用に失敗しました:\n{str(e)}")
            self._update_status("PDF変更適用エラー")
    
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
            initial_folder=os.path.dirname(__file__)
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
        layout = [
            [sg.Text('現在の設定ファイル:')],
            [sg.Text(self.config_file_path or 'デフォルト設定', key='-CONFIG_PATH-')],
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
                if event == '-DETECT-':
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
                    
            except Exception as e:
                logger.error(f"メインループでエラー: {e}")
                logger.error(f"Event: {event}")
                logger.error(f"Values: {values}")
                logger.error(traceback.format_exc())
                # エラーダイアログ表示
                sg.popup_error(f"エラーが発生しました:\n{e}\n\nログファイル: {log_filename}")
        
        logger.info("アプリケーション終了")
        self.window.close()


def main():
    """メイン関数"""
    try:
        app = PresidioPDFGUIMinimal()
        app.run()
    except Exception as e:
        sg.popup_error(f"エラーが発生しました:\n{str(e)}")


if __name__ == "__main__":
    main()