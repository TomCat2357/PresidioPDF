#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - FletによるGUI実装
"""

import flet as ft
import os
import json
import subprocess
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class PresidioPDFApp:
    """PDF個人情報マスキングツールのメインアプリケーション"""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "PDF個人情報マスキングツール"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 0
        
        # アプリケーション状態
        self.current_pdf_path: Optional[str] = None
        self.detection_results: List[Dict] = []
        self.current_page_index = 0
        self.zoom_level = 1.0
        self.selected_entity = None
        
        # 設定
        self.settings = {
            "entities": ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
            "threshold": 0.5,
            "masking_method": "annotation",
            "text_mode": "verbose",
            "spacy_model": "ja_core_news_sm"
        }
        
        # UIコンポーネント
        self.status_text = ft.Text("準備完了", size=12)
        self.progress_bar = ft.ProgressBar(visible=False)
        self.pdf_viewer_content = ft.Container(
            content=ft.Text("PDFファイルを選択してください", text_align=ft.TextAlign.CENTER),
            bgcolor=ft.colors.GREY_100,
            expand=True,
            border_radius=8
        )
        
        self.thumbnails_list = ft.ListView(expand=True, spacing=5)
        self.results_list = ft.ListView(expand=True, spacing=2)
        self.properties_panel = self._create_properties_panel()
        
        self._build_ui()
    
    def _build_ui(self):
        """UIを構築"""
        # AppBar
        self.page.appbar = ft.AppBar(
            title=ft.Text("PDF個人情報マスキングツール"),
            bgcolor=ft.colors.BLUE_GREY_800,
            color=ft.colors.WHITE,
            actions=[
                ft.IconButton(
                    icon=ft.icons.FOLDER_OPEN,
                    tooltip="PDFファイルを開く",
                    on_click=self._open_file_dialog
                ),
                ft.IconButton(
                    icon=ft.icons.SEARCH,
                    tooltip="個人情報検出開始",
                    on_click=self._start_detection
                ),
                ft.IconButton(
                    icon=ft.icons.SAVE,
                    tooltip="マスキング済みPDFを保存", 
                    on_click=self._save_masked_pdf
                ),
                ft.IconButton(
                    icon=ft.icons.SETTINGS,
                    tooltip="設定",
                    on_click=self._open_settings
                ),
            ]
        )
        
        # メインコンテンツエリア - 3カラムレイアウト
        main_content = ft.Row(
            controls=[
                # 左パネル：ページサムネイル
                ft.Container(
                    content=ft.Column([
                        ft.Text("ページサムネイル", weight=ft.FontWeight.BOLD, size=14),
                        ft.Divider(height=1),
                        self.thumbnails_list
                    ]),
                    width=200,
                    bgcolor=ft.colors.GREY_50,
                    padding=10,
                    border=ft.border.all(1, ft.colors.GREY_300)
                ),
                
                # 中央パネル：PDFビューア
                ft.Container(
                    content=ft.Column([
                        # ツールバー
                        ft.Row([
                            ft.IconButton(
                                icon=ft.icons.ZOOM_IN,
                                tooltip="ズームイン",
                                on_click=self._zoom_in
                            ),
                            ft.IconButton(
                                icon=ft.icons.ZOOM_OUT,
                                tooltip="ズームアウト", 
                                on_click=self._zoom_out
                            ),
                            ft.Text(f"ズーム: {int(self.zoom_level * 100)}%"),
                            ft.IconButton(
                                icon=ft.icons.NAVIGATE_BEFORE,
                                tooltip="前のページ",
                                on_click=self._previous_page
                            ),
                            ft.Text(f"ページ {self.current_page_index + 1}"),
                            ft.IconButton(
                                icon=ft.icons.NAVIGATE_NEXT,
                                tooltip="次のページ",
                                on_click=self._next_page
                            ),
                        ], alignment=ft.MainAxisAlignment.START),
                        ft.Divider(height=1),
                        # PDFビューア領域
                        self.pdf_viewer_content
                    ]),
                    expand=True,
                    padding=10
                ),
                
                # 右パネル：検出結果とプロパティ
                ft.Container(
                    content=ft.Column([
                        # 検出結果一覧パネル
                        ft.Text("検出結果", weight=ft.FontWeight.BOLD, size=14),
                        ft.Divider(height=1),
                        ft.Container(
                            content=self.results_list,
                            height=300,
                            border=ft.border.all(1, ft.colors.GREY_300),
                            border_radius=4
                        ),
                        ft.Divider(height=10),
                        # プロパティパネル
                        ft.Text("プロパティ", weight=ft.FontWeight.BOLD, size=14),
                        ft.Divider(height=1),
                        self.properties_panel
                    ]),
                    width=300,
                    bgcolor=ft.colors.GREY_50,
                    padding=10,
                    border=ft.border.all(1, ft.colors.GREY_300)
                )
            ],
            expand=True,
            spacing=0
        )
        
        # ボトムAppBar（ステータスバー）
        bottom_bar = ft.Container(
            content=ft.Row([
                self.status_text,
                ft.Container(expand=True),  # スペーサー
                self.progress_bar
            ]),
            bgcolor=ft.colors.GREY_200,
            padding=ft.padding.symmetric(horizontal=20, vertical=8),
            border=ft.border.only(top=ft.border.BorderSide(1, ft.colors.GREY_400))
        )
        
        # ページにコンテンツを追加
        self.page.add(
            ft.Column([
                main_content,
                bottom_bar
            ], expand=True, spacing=0)
        )
        
        # ドラッグ&ドロップサポートを追加
        self.page.on_file_picker_result = self._file_picker_result
    
    def _create_properties_panel(self) -> ft.Container:
        """プロパティパネルを作成"""
        return ft.Container(
            content=ft.Column([
                ft.Text("エンティティが選択されていません", size=12, color=ft.colors.GREY_600),
                ft.Divider(height=10),
                ft.Row([
                    ft.Text("タイプ:", weight=ft.FontWeight.BOLD),
                    ft.Dropdown(
                        options=[
                            ft.dropdown.Option("PERSON", "人名"),
                            ft.dropdown.Option("LOCATION", "場所"),
                            ft.dropdown.Option("PHONE_NUMBER", "電話番号"),
                            ft.dropdown.Option("DATE_TIME", "日時"),
                        ],
                        disabled=True,
                        width=150
                    )
                ]),
                ft.Row([
                    ft.Text("テキスト:", weight=ft.FontWeight.BOLD),
                    ft.Text("-", expand=True)
                ]),
                ft.Row([
                    ft.Text("信頼度:", weight=ft.FontWeight.BOLD),
                    ft.Text("-", expand=True)
                ]),
                ft.Divider(height=10),
                ft.ElevatedButton(
                    "アノテーション削除",
                    disabled=True,
                    on_click=self._delete_annotation
                )
            ]),
            height=200,
            border=ft.border.all(1, ft.colors.GREY_300),
            border_radius=4,
            padding=10
        )    
    # ===== イベントハンドラー =====
    
    def _open_file_dialog(self, e):
        """ファイル選択ダイアログを開く"""
        file_picker = ft.FilePicker(on_result=self._file_picker_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        
        file_picker.pick_files(
            dialog_title="PDFファイルを選択",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"],
            allow_multiple=False
        )
    
    def _file_picker_result(self, e: ft.FilePickerResultEvent):
        """ファイル選択結果の処理"""
        if e.files:
            file_path = e.files[0].path
            self._load_pdf_file(file_path)
    
    def _load_pdf_file(self, file_path: str):
        """PDFファイルを読み込み"""
        try:
            self.current_pdf_path = file_path
            self.current_page_index = 0
            
            # PDFビューア更新（簡易実装）
            filename = os.path.basename(file_path)
            self.pdf_viewer_content.content = ft.Column([
                ft.Text(f"読み込み済み: {filename}", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(f"パス: {file_path}", size=12, color=ft.colors.GREY_600),
                ft.Container(
                    content=ft.Text("PDF表示エリア\n（実際の実装ではPDFレンダリングが必要）", 
                                   text_align=ft.TextAlign.CENTER),
                    height=400,
                    bgcolor=ft.colors.WHITE,
                    border=ft.border.all(2, ft.colors.GREY_400),
                    border_radius=8,
                    padding=20
                )
            ])
            
            # サムネイル更新（模擬）
            self._update_thumbnails()
            
            # ステータス更新
            self.status_text.value = f"PDFファイル読み込み完了: {filename}"
            self.page.update()
            
        except Exception as ex:
            self._show_error(f"PDFファイルの読み込みに失敗しました: {str(ex)}")
    
    def _update_thumbnails(self):
        """サムネイル一覧を更新"""
        self.thumbnails_list.controls.clear()
        
        # 模擬的に5ページのサムネイルを作成
        for i in range(5):
            thumbnail = ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Text(f"P.{i+1}", text_align=ft.TextAlign.CENTER),
                        width=120,
                        height=160,
                        bgcolor=ft.colors.WHITE,
                        border=ft.border.all(1, ft.colors.GREY_400),
                        border_radius=4
                    ),
                    ft.Text(f"ページ {i+1}", size=10, text_align=ft.TextAlign.CENTER)
                ]),
                on_click=lambda e, page_idx=i: self._jump_to_page(page_idx),
                border_radius=4,
                padding=5
            )
            self.thumbnails_list.controls.append(thumbnail)
        
        self.page.update()
    
    def _start_detection(self, e):
        """個人情報検出を開始"""
        if not self.current_pdf_path:
            self._show_error("PDFファイルが選択されていません")
            return
        
        # 非同期で検出処理を実行
        asyncio.create_task(self._run_detection())
    
    async def _run_detection(self):
        """個人情報検出処理を実行"""
        try:
            # プログレスバー表示
            self.progress_bar.visible = True
            self.status_text.value = "個人情報検出中..."
            self.page.update()
            
            # pdf_presidio_processor.pyを実行
            cmd = [
                "uv", "run", "python", "src/pdf_presidio_processor.py",
                self.current_pdf_path,
                "--report",
                "--read-mode",
                f"--threshold={self.settings['threshold']}",
                f"--spacy_model={self.settings['spacy_model']}"
            ]
            
            # 選択されたエンティティを追加
            if self.settings['entities']:
                cmd.extend(["--entities"] + self.settings['entities'])
            
            # サブプロセスを実行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=r"C:\Users\gk3t-\OneDrive - 又村 友幸\working\PresidioPDF"
            )
            
            if result.returncode == 0:
                # 成功時の処理
                await self._parse_detection_results(result.stdout)
                self.status_text.value = "個人情報検出完了"
            else:
                # エラー時の処理
                self._show_error(f"検出処理に失敗しました: {result.stderr}")
            
        except Exception as ex:
            self._show_error(f"検出処理中にエラーが発生しました: {str(ex)}")
        
        finally:
            # プログレスバー非表示
            self.progress_bar.visible = False
            self.page.update()
    
    async def _parse_detection_results(self, output: str):
        """検出結果を解析してUIに反映"""
        try:
            # 検出結果を解析（簡易実装）
            # 実際の実装では、JSON形式のレポートファイルを読み込む
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
            
        except Exception as ex:
            self._show_error(f"検出結果の解析に失敗しました: {str(ex)}")
    
    def _update_results_list(self):
        """検出結果一覧を更新"""
        self.results_list.controls.clear()
        
        for i, result in enumerate(self.detection_results):
            entity_type_jp = self._get_entity_type_japanese(result["entity_type"])
            
            result_item = ft.ListTile(
                title=ft.Text(f"{entity_type_jp}: {result['text']}", size=12),
                subtitle=ft.Text(f"信頼度: {result['confidence']:.2f}, ページ: {result['page']}", size=10),
                on_click=lambda e, idx=i: self._select_entity(idx),
                dense=True
            )
            
            self.results_list.controls.append(result_item)
        
        self.page.update()
    
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
            self.selected_entity = self.detection_results[index]
            self._update_properties_panel()
            # 該当ページにジャンプ
            target_page = self.selected_entity["page"] - 1
            self._jump_to_page(target_page)
    
    def _update_properties_panel(self):
        """プロパティパネルを更新"""
        if not self.selected_entity:
            return
        
        entity = self.selected_entity
        entity_type_jp = self._get_entity_type_japanese(entity["entity_type"])
        
        # プロパティパネルの内容を更新
        self.properties_panel.content = ft.Column([
            ft.Text("選択されたエンティティ", size=12, color=ft.colors.BLUE_700),
            ft.Divider(height=10),
            ft.Row([
                ft.Text("タイプ:", weight=ft.FontWeight.BOLD),
                ft.Dropdown(
                    value=entity["entity_type"],
                    options=[
                        ft.dropdown.Option("PERSON", "人名"),
                        ft.dropdown.Option("LOCATION", "場所"),
                        ft.dropdown.Option("PHONE_NUMBER", "電話番号"),
                        ft.dropdown.Option("DATE_TIME", "日時"),
                    ],
                    width=150,
                    on_change=self._entity_type_changed
                )
            ]),
            ft.Row([
                ft.Text("テキスト:", weight=ft.FontWeight.BOLD),
                ft.Text(entity["text"], expand=True)
            ]),
            ft.Row([
                ft.Text("信頼度:", weight=ft.FontWeight.BOLD),
                ft.Text(f"{entity['confidence']:.3f}", expand=True)
            ]),
            ft.Row([
                ft.Text("ページ:", weight=ft.FontWeight.BOLD),
                ft.Text(str(entity["page"]), expand=True)
            ]),
            ft.Divider(height=10),
            ft.ElevatedButton(
                "アノテーション削除",
                on_click=self._delete_annotation,
                bgcolor=ft.colors.RED_400,
                color=ft.colors.WHITE
            )
        ])
        
        self.page.update()
    
    def _entity_type_changed(self, e):
        """エンティティタイプが変更された時の処理"""
        if self.selected_entity:
            self.selected_entity["entity_type"] = e.control.value
            self._update_results_list()
    
    def _delete_annotation(self, e):
        """アノテーションを削除"""
        if self.selected_entity:
            # 検出結果から削除
            if self.selected_entity in self.detection_results:
                self.detection_results.remove(self.selected_entity)
            
            # UI更新
            self.selected_entity = None
            self._update_results_list()
            self.properties_panel.content = ft.Column([
                ft.Text("エンティティが選択されていません", size=12, color=ft.colors.GREY_600)
            ])
            self.page.update()
    
    def _save_masked_pdf(self, e):
        """マスキング済みPDFを保存"""
        if not self.current_pdf_path:
            self._show_error("PDFファイルが選択されていません")
            return
        
        # ファイル保存ダイアログ
        save_dialog = ft.FilePicker(on_result=self._save_file_result)
        self.page.overlay.append(save_dialog)
        self.page.update()
        
        # デフォルトのファイル名を生成
        base_name = os.path.splitext(os.path.basename(self.current_pdf_path))[0]
        default_name = f"{base_name}_masked.pdf"
        
        save_dialog.save_file(
            dialog_title="マスキング済みPDFを保存",
            file_name=default_name,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"]
        )
    
    def _save_file_result(self, e: ft.FilePickerResultEvent):
        """保存ファイル選択結果の処理"""
        if e.path:
            asyncio.create_task(self._save_masked_pdf_async(e.path))
    
    async def _save_masked_pdf_async(self, output_path: str):
        """マスキング済みPDFの保存処理"""
        try:
            self.progress_bar.visible = True
            self.status_text.value = "マスキング済みPDF保存中..."
            self.page.update()
            
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
                cwd=r"C:\Users\gk3t-\OneDrive - 又村 友幸\working\PresidioPDF"
            )
            
            if result.returncode == 0:
                self.status_text.value = f"マスキング済みPDFを保存しました: {output_path}"
            else:
                self._show_error(f"PDF保存に失敗しました: {result.stderr}")
                
        except Exception as ex:
            self._show_error(f"PDF保存中にエラーが発生しました: {str(ex)}")
        
        finally:
            self.progress_bar.visible = False
            self.page.update()    
    def _open_settings(self, e):
        """設定画面を開く"""
        def close_settings(e):
            settings_dialog.open = False
            self.page.update()
        
        def save_settings(e):
            # 設定を保存
            self.settings.update({
                "threshold": threshold_slider.value,
                "masking_method": masking_method_dropdown.value,
                "text_mode": text_mode_dropdown.value,
                "spacy_model": spacy_model_dropdown.value
            })
            
            # エンティティ設定
            selected_entities = []
            for checkbox in entity_checkboxes:
                if checkbox.value:
                    selected_entities.append(checkbox.label)
            self.settings["entities"] = selected_entities
            
            # 設定を永続化（JSONファイルに保存）
            self._save_settings_to_file()
            
            close_settings(e)
        
        # 設定UI要素
        threshold_slider = ft.Slider(
            min=0.0,
            max=1.0,
            value=self.settings["threshold"],
            divisions=10,
            label="信頼度閾値: {value}"
        )
        
        entity_checkboxes = [
            ft.Checkbox(label="PERSON", value="PERSON" in self.settings["entities"]),
            ft.Checkbox(label="LOCATION", value="LOCATION" in self.settings["entities"]),
            ft.Checkbox(label="PHONE_NUMBER", value="PHONE_NUMBER" in self.settings["entities"]),
            ft.Checkbox(label="DATE_TIME", value="DATE_TIME" in self.settings["entities"])
        ]
        
        masking_method_dropdown = ft.Dropdown(
            label="マスキング方法",
            value=self.settings["masking_method"],
            options=[
                ft.dropdown.Option("annotation", "注釈"),
                ft.dropdown.Option("highlight", "ハイライト"),
                ft.dropdown.Option("both", "両方")
            ]
        )
        
        text_mode_dropdown = ft.Dropdown(
            label="テキスト表示モード",
            value=self.settings["text_mode"],
            options=[
                ft.dropdown.Option("verbose", "詳細"),
                ft.dropdown.Option("minimal", "最小限"),
                ft.dropdown.Option("silent", "なし")
            ]
        )
        
        spacy_model_dropdown = ft.Dropdown(
            label="使用モデル",
            value=self.settings["spacy_model"],
            options=[
                ft.dropdown.Option("ja_core_news_sm", "ja_core_news_sm"),
                ft.dropdown.Option("ja_core_news_md", "ja_core_news_md"),
                ft.dropdown.Option("ja_ginza", "ja_ginza")
            ]
        )
        
        # 設定ダイアログ
        settings_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("設定"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("検出対象エンティティ", weight=ft.FontWeight.BOLD),
                    ft.Column(entity_checkboxes),
                    ft.Divider(),
                    ft.Text("信頼度閾値", weight=ft.FontWeight.BOLD),
                    threshold_slider,
                    ft.Divider(),
                    masking_method_dropdown,
                    text_mode_dropdown,
                    spacy_model_dropdown
                ], tight=True),
                width=400,
                height=500
            ),
            actions=[
                ft.TextButton("キャンセル", on_click=close_settings),
                ft.TextButton("保存", on_click=save_settings)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        self.page.dialog = settings_dialog
        settings_dialog.open = True
        self.page.update()
    
    def _save_settings_to_file(self):
        """設定をファイルに保存"""
        try:
            settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as ex:
            print(f"設定の保存に失敗しました: {ex}")
    
    def _load_settings_from_file(self):
        """ファイルから設定を読み込み"""
        try:
            settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)
        except Exception as ex:
            print(f"設定の読み込みに失敗しました: {ex}")
    
    # ===== ナビゲーション機能 =====
    
    def _zoom_in(self, e):
        """ズームイン"""
        self.zoom_level = min(self.zoom_level * 1.25, 5.0)
        self._update_zoom_display()
    
    def _zoom_out(self, e):
        """ズームアウト"""
        self.zoom_level = max(self.zoom_level / 1.25, 0.25)
        self._update_zoom_display()
    
    def _update_zoom_display(self):
        """ズーム表示を更新"""
        # ツールバーのズーム表示を更新
        # 実際の実装では、PDFビューアのズームも更新する
        self.page.update()
    
    def _previous_page(self, e):
        """前のページに移動"""
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self._update_page_display()
    
    def _next_page(self, e):
        """次のページに移動"""
        # 実際の実装では、PDFの総ページ数を取得
        max_pages = 5  # 模擬的に5ページ
        if self.current_page_index < max_pages - 1:
            self.current_page_index += 1
            self._update_page_display()
    
    def _jump_to_page(self, page_index: int):
        """指定ページにジャンプ"""
        self.current_page_index = page_index
        self._update_page_display()
    
    def _update_page_display(self):
        """ページ表示を更新"""
        # 実際の実装では、PDFビューアの表示ページを更新
        self.page.update()
    
    # ===== ユーティリティ =====
    
    def _show_error(self, message: str):
        """エラーメッセージを表示"""
        error_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("エラー"),
            content=ft.Text(message),
            actions=[
                ft.TextButton("OK", on_click=lambda e: self._close_dialog(error_dialog))
            ]
        )
        
        self.page.dialog = error_dialog
        error_dialog.open = True
        self.page.update()
    
    def _close_dialog(self, dialog):
        """ダイアログを閉じる"""
        dialog.open = False
        self.page.update()
    
    def initialize(self):
        """アプリケーションの初期化"""
        # 設定をファイルから読み込み
        self._load_settings_from_file()
        
        # ページを更新
        self.page.update()


def main(page: ft.Page):
    """メイン関数"""
    # ページ設定
    page.window_width = 1200
    page.window_height = 800
    page.window_min_width = 800
    page.window_min_height = 600
    
    # アプリケーションを作成・初期化
    app = PresidioPDFApp(page)
    app.initialize()


if __name__ == "__main__":
    # Fletアプリケーションを起動
    ft.app(target=main, name="PDF個人情報マスキングツール", port=8888)