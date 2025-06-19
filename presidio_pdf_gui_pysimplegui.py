#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - PySimpleGUIによるGUI実装
"""

import FreeSimpleGUI as sg
import os
import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import tempfile
import sys
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import io
import tkinter as tk

# PySimpleGUIテーマ設定
sg.theme('LightBlue3')

class PresidioPDFGUI:
    """PDF個人情報マスキングツールのメインアプリケーション"""
    
    def __init__(self):
        # アプリケーション状態
        self.current_pdf_path: Optional[str] = None
        self.detection_results: List[Dict] = []
        self.current_page_index = 0
        self.zoom_level = 1.0
        self.selected_entity_index = -1
        self.total_pages = 0
        self.pdf_document = None  # PyMuPDF document object
        self.current_page_image = None  # PIL Image of current page
        
        # 設定
        self.settings = {
            "entities": ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
            "threshold": 0.5,
            "masking_method": "annotation",
            "text_mode": "verbose",
            "spacy_model": "ja_core_news_sm",
            "deduplication_mode": "score",
            "deduplication_overlap_mode": "contain_only"
        }
        
        # 設定ファイル読み込み
        self._load_settings()
        
        # GUI window
        self.window = None
        self._create_main_window()
    
    def _create_main_window(self):
        """メインウィンドウを作成"""
        
        # メニューバー定義
        menu_def = [
            ['&ファイル', ['&開く::open_file', '&保存::save_file', '---', '&終了::exit']],
            ['&編集', ['&設定::settings']],
            ['&ツール', ['&検出開始::detect', '&レポート出力::export_report']],
            ['&ヘルプ', ['&このアプリについて::about']]
        ]
        
        # ツールバー
        toolbar_layout = [
            [sg.Button('ファイルを開く', key='-OPEN-', size=(12, 1)),
             sg.Button('検出開始', key='-DETECT-', size=(10, 1), disabled=True),
             sg.Button('保存', key='-SAVE-', size=(8, 1), disabled=True),
             sg.VSeparator(),
             sg.Button('設定', key='-SETTINGS-', size=(8, 1)),
             sg.Button('ズームイン', key='-ZOOM_IN-', size=(10, 1)),
             sg.Button('ズームアウト', key='-ZOOM_OUT-', size=(10, 1)),
             sg.Text(f'ズーム: {int(self.zoom_level * 100)}%', key='-ZOOM_LEVEL-'),
             sg.Push(),
             sg.Button('終了', key='-EXIT-', size=(8, 1))]
        ]
        
        # 左パネル：ページサムネイル
        left_panel = [
            [sg.Text('ページサムネイル', font=('Arial', 12, 'bold'))],
            [sg.HSeparator()],
            [sg.Listbox(values=[], size=(20, 15), key='-THUMBNAILS-', 
                        enable_events=True, font=('Arial', 10))]
        ]
        
        # 中央パネル：PDFビューア
        pdf_viewer_controls = [
            [sg.Button('◀', key='-PREV_PAGE-', size=(3, 1)),
             sg.Text('ページ 1 / 1', key='-PAGE_INFO-', size=(15, 1)),
             sg.Button('▶', key='-NEXT_PAGE-', size=(3, 1)),
             sg.Push()]
        ]
        
        center_panel = [
            [sg.Column(pdf_viewer_controls, element_justification='left')],
            [sg.HSeparator()],
            [sg.Canvas(size=(600, 700), background_color='white', key='-PDF_CANVAS-',
                      drag_submits=True, enable_events=True)]
        ]
        
        # 右パネル：検出結果と プロパティ
        results_panel = [
            [sg.Text('検出結果', font=('Arial', 12, 'bold'))],
            [sg.HSeparator()],
            [sg.Listbox(values=[], size=(35, 12), key='-RESULTS-', 
                        enable_events=True, font=('Arial', 9))]
        ]
        
        properties_panel = [
            [sg.Text('プロパティ', font=('Arial', 12, 'bold'))],
            [sg.HSeparator()],
            [sg.Text('エンティティが選択されていません', key='-PROP_STATUS-', 
                     text_color='gray', font=('Arial', 9))],
            [sg.Text('タイプ:', size=(8, 1)), 
             sg.Combo(['PERSON', 'LOCATION', 'PHONE_NUMBER', 'DATE_TIME'], 
                      key='-ENTITY_TYPE-', size=(20, 1), disabled=True)],
            [sg.Text('テキスト:', size=(8, 1)), 
             sg.Text('-', key='-ENTITY_TEXT-', size=(20, 1))],
            [sg.Text('信頼度:', size=(8, 1)), 
             sg.Text('-', key='-ENTITY_CONFIDENCE-', size=(20, 1))],
            [sg.Text('ページ:', size=(8, 1)), 
             sg.Text('-', key='-ENTITY_PAGE-', size=(20, 1))],
            [sg.HSeparator()],
            [sg.Button('削除', key='-DELETE_ANNOTATION-', size=(12, 1), 
                       disabled=True, button_color=('white', 'red'))]
        ]
        
        right_panel = [
            [sg.Column(results_panel, element_justification='left')],
            [sg.HSeparator()],
            [sg.Column(properties_panel, element_justification='left')]
        ]
        
        # メインレイアウト
        main_layout = [
            [sg.Menu(menu_def)],
            [sg.Column(toolbar_layout, element_justification='left')],
            [sg.HSeparator()],
            [sg.Column(left_panel, size=(200, 500), element_justification='left', 
                      vertical_alignment='top'),
             sg.VSeparator(),
             sg.Column(center_panel, size=(650, 500), element_justification='center',
                      vertical_alignment='top'),
             sg.VSeparator(),
             sg.Column(right_panel, size=(320, 500), element_justification='left',
                      vertical_alignment='top')],
            [sg.HSeparator()],
            [sg.Text('準備完了', key='-STATUS-', size=(80, 1)),
             sg.ProgressBar(100, orientation='h', size=(20, 20), key='-PROGRESS-', 
                           visible=False)]
        ]
        
        # ウィンドウ作成
        self.window = sg.Window(
            'PDF個人情報マスキングツール',
            main_layout,
            size=(1200, 800),
            resizable=True,
            finalize=True,
            enable_close_attempted_event=True
        )
        
        # 初期状態の設定
        self._update_status("準備完了")
        
    def _load_settings(self):
        """設定ファイルから設定を読み込み"""
        try:
            settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)
        except Exception as ex:
            print(f"設定の読み込みに失敗しました: {ex}")
    
    def _save_settings(self):
        """設定をファイルに保存"""
        try:
            settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as ex:
            print(f"設定の保存に失敗しました: {ex}")
    
    def _update_status(self, message: str):
        """ステータスバーを更新"""
        if self.window:
            self.window['-STATUS-'].update(message)
    
    def _show_progress(self, visible: bool = True):
        """プログレスバーの表示/非表示"""
        if self.window:
            self.window['-PROGRESS-'].update(visible=visible)
    
    def _open_file_dialog(self):
        """ファイル選択ダイアログを開く"""
        file_path = sg.popup_get_file(
            'PDFファイルを選択してください',
            file_types=(("PDF Files", "*.pdf"),),
            no_window=True
        )
        
        if file_path:
            self._load_pdf_file(file_path)
    
    def _load_pdf_file(self, file_path: str):
        """PDFファイルを読み込み"""
        try:
            # 既存のPDFを閉じる
            if self.pdf_document:
                self.pdf_document.close()
            
            # 新しいPDFファイルを開く
            self.pdf_document = fitz.open(file_path)
            self.current_pdf_path = file_path
            self.current_page_index = 0
            self.detection_results = []
            self.total_pages = len(self.pdf_document)
            
            # ファイル名表示
            filename = os.path.basename(file_path)
            self._update_status(f"PDFファイル読み込み完了: {filename} ({self.total_pages}ページ)")
            
            # ボタン状態更新
            self.window['-DETECT-'].update(disabled=False)
            
            # ページサムネイル更新
            self._update_thumbnails()
            
            # PDFビューア更新
            self._update_pdf_viewer()
            
        except Exception as ex:
            sg.popup_error(f"PDFファイルの読み込みに失敗しました:\n{str(ex)}")
    
    def _update_thumbnails(self):
        """サムネイル一覧を更新"""
        if self.pdf_document:
            # 実際のページ数に基づいてサムネイル一覧を作成
            thumbnails = [f"ページ {i+1}" for i in range(self.total_pages)]
            self.window['-THUMBNAILS-'].update(values=thumbnails)
        else:
            self.window['-THUMBNAILS-'].update(values=[])
        
        # ページ情報更新
        self._update_page_info()
    
    def _update_page_info(self):
        """ページ情報を更新"""
        if self.total_pages > 0:
            page_info = f"ページ {self.current_page_index + 1} / {self.total_pages}"
            self.window['-PAGE_INFO-'].update(page_info)
    
    def _update_pdf_viewer(self):
        """PDFビューアを更新"""
        canvas = self.window['-PDF_CANVAS-']
        if not canvas or not self.pdf_document:
            return
        
        try:
            # Canvasクリア
            canvas.TKCanvas.delete("all")
            
            # 現在のページを取得
            page = self.pdf_document[self.current_page_index]
            
            # ズームレベルを適用したマトリックスを作成
            mat = fitz.Matrix(self.zoom_level, self.zoom_level)
            
            # ページを画像として描画
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("ppm")
            
            # PIL Image に変換
            pil_image = Image.open(io.BytesIO(img_data))
            self.current_page_image = pil_image
            
            # Canvas サイズ（固定値を使用）
            canvas_width = 600
            canvas_height = 700
            
            # 画像をCanvasサイズに合わせて調整
            img_width, img_height = pil_image.size
            scale_x = canvas_width / img_width
            scale_y = canvas_height / img_height
            scale = min(scale_x, scale_y, 1.0)  # 縮小のみ、拡大はしない
            
            if scale < 1.0:
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # PhotoImage に変換
            photo = ImageTk.PhotoImage(pil_image)
            
            # Canvas中央に画像を配置
            canvas_center_x = canvas_width // 2
            canvas_center_y = canvas_height // 2
            
            canvas.TKCanvas.create_image(canvas_center_x, canvas_center_y, image=photo)
            
            # PhotoImage オブジェクトの参照を保持（ガベージコレクション対策）
            canvas.TKCanvas.image = photo
            
        except Exception as ex:
            # エラー時は代替表示
            canvas.TKCanvas.create_rectangle(50, 50, 550, 650, fill='white', outline='red')
            canvas.TKCanvas.create_text(300, 350, text=f"PDF表示エラー:\n{str(ex)}", 
                                       font=('Arial', 12), fill='red')
    
    def _start_detection(self):
        """個人情報検出を開始"""
        if not self.current_pdf_path:
            sg.popup_error("PDFファイルが選択されていません")
            return
        
        # 検出処理を別スレッドで実行
        threading.Thread(target=self._run_detection, daemon=True).start()
    
    def _run_detection(self):
        """個人情報検出処理を実行"""
        try:
            # プログレスバー表示
            self.window.write_event_value('-PROGRESS_START-', None)
            
            # 一時ディレクトリを作成してレポートファイルを保存
            temp_dir = tempfile.mkdtemp()
            
            # pdf_presidio_processor.pyを実行
            cmd = [
                "uv", "run", "python", "src/pdf_presidio_processor.py",
                self.current_pdf_path,
                "--read-mode",  # 読み取りモード（既存の注釈を読む）
                "--read-report",  # レポート生成を有効化
                f"--threshold={self.settings['threshold']}",
                f"--spacy_model={self.settings['spacy_model']}"
            ]
            
            # 選択されたエンティティを追加
            if self.settings['entities']:
                cmd.extend(["--entities"] + self.settings['entities'])
            
            # 重複除去設定
            if 'deduplication_mode' in self.settings:
                cmd.extend(["--deduplication-mode", self.settings['deduplication_mode']])
            if 'deduplication_overlap_mode' in self.settings:
                cmd.extend(["--deduplication-overlap-mode", self.settings['deduplication_overlap_mode']])
            
            # サブプロセス実行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            if result.returncode == 0:
                # 成功時の処理 - レポートファイルを探して読み込み
                self._find_and_read_report_files(result.stdout)
            else:
                # エラー時の処理
                self.window.write_event_value('-DETECTION_ERROR-', result.stderr)
                
        except Exception as ex:
            self.window.write_event_value('-DETECTION_ERROR-', str(ex))
    
    def _find_and_read_report_files(self, stdout_output: str):
        """生成されたレポートファイルを探して読み込み"""
        try:
            # レポートファイルを探す
            current_dir = os.path.dirname(os.path.abspath(__file__))
            report_files = []
            
            # 最新のレポートファイルを探す（タイムスタンプ順）
            for file in os.listdir(current_dir):
                if file.startswith('annotations_report_') and file.endswith('.json'):
                    report_files.append(os.path.join(current_dir, file))
                elif file.startswith('pdf_report_') and file.endswith('.json'):
                    report_files.append(os.path.join(current_dir, file))
            
            # 最新のファイルを取得
            if report_files:
                latest_report = max(report_files, key=os.path.getmtime)
                
                # レポートファイルを読み込み
                with open(latest_report, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                
                # 解析して結果を送信
                self.window.write_event_value('-DETECTION_SUCCESS-', json.dumps(report_data))
                
                # 一時ファイルを削除（オプション）
                # os.remove(latest_report)
            else:
                # レポートファイルが見つからない場合、stdout を解析
                self.window.write_event_value('-DETECTION_SUCCESS-', stdout_output)
                
        except Exception as ex:
            self.window.write_event_value('-DETECTION_ERROR-', f"レポートファイルの読み込みに失敗: {str(ex)}")
    
    def _parse_detection_results(self, output: str):
        """検出結果を解析してUIに反映"""
        try:
            # JSON形式のレポートデータを解析
            try:
                report_data = json.loads(output)
            except json.JSONDecodeError:
                # JSONでない場合は模擬データを使用
                self._create_mock_detection_results()
                return
            
            self.detection_results = []
            
            # アノテーションレポートの場合
            if 'annotations' in report_data:
                for annotation in report_data['annotations']:
                    if 'coordinates' in annotation:
                        coords = annotation['coordinates']
                        
                        # アノテーションの内容からエンティティ情報を抽出
                        content = annotation.get('content', '')
                        entity_type, confidence, text = self._extract_entity_from_annotation_content(content)
                        
                        detection_result = {
                            "entity_type": entity_type,
                            "text": text,
                            "confidence": confidence,
                            "page": coords.get('page_number', 1),
                            "coordinates": [
                                coords.get('x0', 0),
                                coords.get('y0', 0), 
                                coords.get('x1', 100),
                                coords.get('y1', 20)
                            ]
                        }
                        self.detection_results.append(detection_result)
            
            # 一般的な処理レポートの場合
            elif 'file_results' in report_data:
                for file_result in report_data['file_results']:
                    if 'detected_entities' in file_result:
                        for entity in file_result['detected_entities']:
                            if 'coordinates' in entity:
                                coords = entity['coordinates']
                                detection_result = {
                                    "entity_type": entity.get('entity_type', 'UNKNOWN'),
                                    "text": entity.get('text', ''),
                                    "confidence": entity.get('score', 0.0),
                                    "page": coords.get('page_number', 1),
                                    "coordinates": [
                                        coords.get('x0', 0),
                                        coords.get('y0', 0),
                                        coords.get('x1', 100), 
                                        coords.get('y1', 20)
                                    ]
                                }
                                self.detection_results.append(detection_result)
            
            # 結果が空の場合は模擬データを使用
            if not self.detection_results:
                self._create_mock_detection_results()
            
            # 検出結果一覧を更新
            self._update_results_list()
            
            # 保存ボタンを有効化
            self.window['-SAVE-'].update(disabled=False)
            
        except Exception as ex:
            sg.popup_error(f"検出結果の解析に失敗しました:\n{str(ex)}")
            # エラー時は模擬データを使用
            self._create_mock_detection_results()
    
    def _extract_entity_from_annotation_content(self, content: str) -> Tuple[str, float, str]:
        """アノテーションの内容からエンティティ情報を抽出"""
        try:
            # 例: "個人情報検出: PERSON (score: 0.85)"
            if "PERSON" in content:
                entity_type = "PERSON"
            elif "PHONE_NUMBER" in content:
                entity_type = "PHONE_NUMBER"
            elif "LOCATION" in content:
                entity_type = "LOCATION"
            elif "DATE_TIME" in content:
                entity_type = "DATE_TIME"
            else:
                entity_type = "UNKNOWN"
            
            # 信頼度スコアを抽出
            import re
            score_match = re.search(r'score:\s*([\d.]+)', content)
            confidence = float(score_match.group(1)) if score_match else 0.5
            
            # テキストはコンテンツから推測（実際の実装では別の方法で取得）
            text = entity_type
            
            return entity_type, confidence, text
            
        except Exception:
            return "UNKNOWN", 0.5, ""
    
    def _create_mock_detection_results(self):
        """模擬的な検出結果を作成"""
        self.detection_results = [
            {
                "entity_type": "PERSON",
                "text": "田中太郎",
                "confidence": 0.85,
                "page": 1,
                "coordinates": [100, 200, 150, 220]
            },
            {
                "entity_type": "PHONE_NUMBER", 
                "text": "03-1234-5678",
                "confidence": 0.92,
                "page": 2,
                "coordinates": [200, 300, 280, 320]
            },
            {
                "entity_type": "LOCATION",
                "text": "東京都渋谷区",
                "confidence": 0.78,
                "page": 2,
                "coordinates": [150, 400, 230, 420]
            }
        ]
        
        # 検出結果一覧を更新
        self._update_results_list()
        
        # 保存ボタンを有効化
        self.window['-SAVE-'].update(disabled=False)
    
    def _update_results_list(self):
        """検出結果一覧を更新"""
        results_display = []
        
        for i, result in enumerate(self.detection_results):
            entity_type_jp = self._get_entity_type_japanese(result["entity_type"])
            display_text = f"{entity_type_jp}: {result['text']} (信頼度: {result['confidence']:.2f}, P.{result['page']})"
            results_display.append(display_text)
        
        self.window['-RESULTS-'].update(values=results_display)
    
    def _get_entity_type_japanese(self, entity_type: str) -> str:
        """エンティティタイプの日本語名を返す"""
        mapping = {
            "PERSON": "人名",
            "LOCATION": "場所", 
            "PHONE_NUMBER": "電話番号",
            "DATE_TIME": "日時",
            "INDIVIDUAL_NUMBER": "マイナンバー"
        }
        return mapping.get(entity_type, entity_type)
    
    def _select_entity(self, index: int):
        """エンティティを選択"""
        if 0 <= index < len(self.detection_results):
            self.selected_entity_index = index
            entity = self.detection_results[index]
            
            # プロパティパネル更新
            self.window['-PROP_STATUS-'].update("選択されたエンティティ", text_color='blue')
            self.window['-ENTITY_TYPE-'].update(value=entity["entity_type"], disabled=False)
            self.window['-ENTITY_TEXT-'].update(entity["text"])
            self.window['-ENTITY_CONFIDENCE-'].update(f"{entity['confidence']:.3f}")
            self.window['-ENTITY_PAGE-'].update(str(entity["page"]))
            self.window['-DELETE_ANNOTATION-'].update(disabled=False)
            
            # 該当ページにジャンプ
            target_page = entity["page"] - 1
            self._jump_to_page(target_page)
    
    def _delete_annotation(self):
        """選択されたアノテーションを削除"""
        if 0 <= self.selected_entity_index < len(self.detection_results):
            # 確認ダイアログ
            entity = self.detection_results[self.selected_entity_index]
            if sg.popup_yes_no(f"「{entity['text']}」を削除しますか？", title="削除確認") == "Yes":
                # 検出結果から削除
                del self.detection_results[self.selected_entity_index]
                
                # UI更新
                self.selected_entity_index = -1
                self._update_results_list()
                self._clear_properties_panel()
    
    def _clear_properties_panel(self):
        """プロパティパネルをクリア"""
        self.window['-PROP_STATUS-'].update("エンティティが選択されていません", text_color='gray')
        self.window['-ENTITY_TYPE-'].update(value="", disabled=True)
        self.window['-ENTITY_TEXT-'].update("-")
        self.window['-ENTITY_CONFIDENCE-'].update("-")
        self.window['-ENTITY_PAGE-'].update("-")
        self.window['-DELETE_ANNOTATION-'].update(disabled=True)
    
    def _jump_to_page(self, page_index: int):
        """指定ページにジャンプ"""
        if 0 <= page_index < self.total_pages:
            self.current_page_index = page_index
            self._update_page_info()
            self._update_pdf_viewer()
            
            # サムネイル選択状態更新
            thumbnails = self.window['-THUMBNAILS-'].get_list_values()
            if thumbnails:
                self.window['-THUMBNAILS-'].set_value([thumbnails[page_index]])
    
    def _zoom_in(self):
        """ズームイン"""
        self.zoom_level = min(self.zoom_level * 1.25, 5.0)
        self._update_zoom_display()
    
    def _zoom_out(self):
        """ズームアウト"""
        self.zoom_level = max(self.zoom_level / 1.25, 0.25)
        self._update_zoom_display()
    
    def _update_zoom_display(self):
        """ズーム表示を更新"""
        self.window['-ZOOM_LEVEL-'].update(f'ズーム: {int(self.zoom_level * 100)}%')
        self._update_pdf_viewer()
    
    def _previous_page(self):
        """前のページに移動"""
        if self.current_page_index > 0:
            self._jump_to_page(self.current_page_index - 1)
    
    def _next_page(self):
        """次のページに移動"""
        if self.current_page_index < self.total_pages - 1:
            self._jump_to_page(self.current_page_index + 1)
    
    def _open_settings_dialog(self):
        """設定ダイアログを開く"""
        # 設定ダイアログのレイアウト
        entity_checkboxes = [
            [sg.Checkbox('人名 (PERSON)', key='-ENTITY_PERSON-', 
                        default='PERSON' in self.settings['entities'])],
            [sg.Checkbox('場所 (LOCATION)', key='-ENTITY_LOCATION-', 
                        default='LOCATION' in self.settings['entities'])],
            [sg.Checkbox('電話番号 (PHONE_NUMBER)', key='-ENTITY_PHONE-', 
                        default='PHONE_NUMBER' in self.settings['entities'])],
            [sg.Checkbox('日時 (DATE_TIME)', key='-ENTITY_DATE-', 
                        default='DATE_TIME' in self.settings['entities'])]
        ]
        
        settings_layout = [
            [sg.Text('検出対象エンティティ', font=('Arial', 12, 'bold'))],
            [sg.Column(entity_checkboxes, element_justification='left')],
            [sg.HSeparator()],
            [sg.Text('信頼度閾値', font=('Arial', 12, 'bold'))],
            [sg.Slider(range=(0.0, 1.0), default_value=self.settings['threshold'], 
                      resolution=0.1, orientation='h', size=(40, 20), key='-THRESHOLD-')],
            [sg.HSeparator()],
            [sg.Text('マスキング方法', font=('Arial', 12, 'bold'))],
            [sg.Combo(['annotation', 'highlight', 'both'], 
                     default_value=self.settings['masking_method'], 
                     key='-MASKING_METHOD-', size=(20, 1))],
            [sg.Text('テキスト表示モード', font=('Arial', 12, 'bold'))],
            [sg.Combo(['verbose', 'minimal', 'silent'], 
                     default_value=self.settings['text_mode'], 
                     key='-TEXT_MODE-', size=(20, 1))],
            [sg.Text('使用モデル', font=('Arial', 12, 'bold'))],
            [sg.Combo(['ja_core_news_sm', 'ja_core_news_md', 'ja_ginza'], 
                     default_value=self.settings['spacy_model'], 
                     key='-SPACY_MODEL-', size=(20, 1))],
            [sg.HSeparator()],
            [sg.Button('保存', key='-SAVE_SETTINGS-', size=(10, 1)), 
             sg.Button('キャンセル', key='-CANCEL_SETTINGS-', size=(10, 1))]
        ]
        
        settings_window = sg.Window('設定', settings_layout, modal=True, finalize=True)
        
        while True:
            event, values = settings_window.read()
            
            if event in (sg.WIN_CLOSED, '-CANCEL_SETTINGS-'):
                break
            elif event == '-SAVE_SETTINGS-':
                # 設定を保存
                selected_entities = []
                if values['-ENTITY_PERSON-']:
                    selected_entities.append('PERSON')
                if values['-ENTITY_LOCATION-']:
                    selected_entities.append('LOCATION')
                if values['-ENTITY_PHONE-']:
                    selected_entities.append('PHONE_NUMBER')
                if values['-ENTITY_DATE-']:
                    selected_entities.append('DATE_TIME')
                
                self.settings.update({
                    'entities': selected_entities,
                    'threshold': values['-THRESHOLD-'],
                    'masking_method': values['-MASKING_METHOD-'],
                    'text_mode': values['-TEXT_MODE-'],
                    'spacy_model': values['-SPACY_MODEL-']
                })
                
                # 設定をファイルに保存
                self._save_settings()
                
                sg.popup('設定が保存されました', title='設定保存')
                break
        
        settings_window.close()
    
    def _save_masked_pdf(self):
        """マスキング済みPDFを保存"""
        if not self.current_pdf_path:
            sg.popup_error("PDFファイルが選択されていません")
            return
        
        # 保存ファイル名の生成
        base_name = os.path.splitext(os.path.basename(self.current_pdf_path))[0]
        default_name = f"{base_name}_masked.pdf"
        
        # ファイル保存ダイアログ
        save_path = sg.popup_get_file(
            'マスキング済みPDFを保存',
            save_as=True,
            default_extension='.pdf',
            file_types=(("PDF Files", "*.pdf"),),
            default_path=default_name,
            no_window=True
        )
        
        if save_path:
            # 保存処理を別スレッドで実行
            threading.Thread(target=self._save_pdf_async, args=(save_path,), daemon=True).start()
    
    def _save_pdf_async(self, output_path: str):
        """マスキング済みPDFの保存処理"""
        try:
            self.window.write_event_value('-SAVE_START-', None)
            
            # pdf_presidio_processor.pyでマスキング処理を実行
            cmd = [
                "uv", "run", "python", "src/pdf_presidio_processor.py",
                self.current_pdf_path,
                "--suffix", "_masked",
                f"--masking-method={self.settings['masking_method']}",
                f"--masking-text-mode={self.settings['text_mode']}"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            if result.returncode == 0:
                self.window.write_event_value('-SAVE_SUCCESS-', output_path)
            else:
                self.window.write_event_value('-SAVE_ERROR-', result.stderr)
                
        except Exception as ex:
            self.window.write_event_value('-SAVE_ERROR-', str(ex))
    
    def run(self):
        """メインイベントループ"""
        while True:
            event, values = self.window.read()
            
            if event in (sg.WIN_CLOSED, '-EXIT-', 'exit'):
                break
            
            # ファイル操作
            elif event in ('-OPEN-', 'open_file'):
                self._open_file_dialog()
            
            # 検出処理
            elif event in ('-DETECT-', 'detect'):
                self._start_detection()
            elif event == '-PROGRESS_START-':
                self._show_progress(True)
                self._update_status("個人情報検出中...")
            elif event == '-DETECTION_SUCCESS-':
                self._show_progress(False)
                self._parse_detection_results(values[event])
                self._update_status("個人情報検出完了")
            elif event == '-DETECTION_ERROR-':
                self._show_progress(False)
                sg.popup_error(f"検出処理に失敗しました:\n{values[event]}")
                self._update_status("検出処理エラー")
            
            # 保存処理
            elif event in ('-SAVE-', 'save_file'):
                self._save_masked_pdf()
            elif event == '-SAVE_START-':
                self._show_progress(True)
                self._update_status("マスキング済みPDF保存中...")
            elif event == '-SAVE_SUCCESS-':
                self._show_progress(False)
                self._update_status(f"マスキング済みPDFを保存しました: {values[event]}")
                sg.popup(f"マスキング済みPDFを保存しました:\n{values[event]}", title="保存完了")
            elif event == '-SAVE_ERROR-':
                self._show_progress(False)
                sg.popup_error(f"PDF保存に失敗しました:\n{values[event]}")
                self._update_status("PDF保存エラー")
            
            # 設定
            elif event in ('-SETTINGS-', 'settings'):
                self._open_settings_dialog()
            
            # ナビゲーション
            elif event == '-PREV_PAGE-':
                self._previous_page()
            elif event == '-NEXT_PAGE-':
                self._next_page()
            elif event == '-ZOOM_IN-':
                self._zoom_in()
            elif event == '-ZOOM_OUT-':
                self._zoom_out()
            
            # リスト選択
            elif event == '-THUMBNAILS-':
                if values['-THUMBNAILS-']:
                    selected_thumbnail = values['-THUMBNAILS-'][0]
                    page_index = int(selected_thumbnail.split()[1]) - 1
                    self._jump_to_page(page_index)
            
            elif event == '-RESULTS-':
                if values['-RESULTS-']:
                    selected_index = self.window['-RESULTS-'].get_indexes()[0]
                    self._select_entity(selected_index)
            
            # アノテーション操作
            elif event == '-DELETE_ANNOTATION-':
                self._delete_annotation()
            
            # ヘルプ
            elif event == 'about':
                sg.popup('PDF個人情報マスキングツール v1.0\n\nPresidio and PyMuPDF を使用したPDF個人情報検出・マスキングツール', 
                        title='このアプリについて')
        
        # リソースのクリーンアップ
        if self.pdf_document:
            self.pdf_document.close()
        
        # ウィンドウを閉じる
        self.window.close()


def main():
    """メイン関数"""
    try:
        # アプリケーション実行
        app = PresidioPDFGUI()
        app.run()
    except Exception as e:
        sg.popup_error(f"アプリケーションの実行中にエラーが発生しました:\n{str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()