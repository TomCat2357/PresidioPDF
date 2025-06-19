#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - FletによるGUI実装（シンプル版）
"""

import flet as ft
import os
import json
import subprocess
import asyncio
import base64
import io
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("PyMuPDFが利用できません。PDFビューア機能は制限されます。")


class PDFViewer:
    """PDFビューアクラス"""
    
    def __init__(self):
        self.document = None
        self.current_page = 0
        self.zoom_level = 1.0
        self.page_images = []
    
    def load_pdf(self, file_path: str) -> bool:
        """PDFファイルを読み込み"""
        if not PYMUPDF_AVAILABLE:
            return False
        
        try:
            self.document = fitz.open(file_path)
            self.current_page = 0
            self.page_images.clear()
            return True
        except Exception as e:
            print(f"PDF読み込みエラー: {e}")
            return False
    
    def get_page_count(self) -> int:
        """総ページ数を取得"""
        if self.document:
            return len(self.document)
        return 0
    
    def render_page(self, page_num: int, zoom: float = 1.0) -> Optional[str]:
        """指定ページを画像として描画し、base64エンコードされた文字列を返す"""
        if not self.document or page_num >= len(self.document):
            return None
        
        try:
            page = self.document[page_num]
            # 解像度を設定（zoom倍率を適用）
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            
            # PNG形式でバイト配列に変換
            img_data = pix.tobytes("png")
            
            # base64エンコード
            img_base64 = base64.b64encode(img_data).decode()
            
            return f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            print(f"ページ描画エラー: {e}")
            return None
    
    def render_thumbnail(self, page_num: int, width: int = 100) -> Optional[str]:
        """サムネイルを生成"""
        if not self.document or page_num >= len(self.document):
            return None
        
        try:
            page = self.document[page_num]
            # サムネイル用の小さなサイズで描画
            rect = page.rect
            zoom = width / rect.width
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            
            img_data = pix.tobytes("png")
            img_base64 = base64.b64encode(img_data).decode()
            
            return f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            print(f"サムネイル生成エラー: {e}")
            return None


class PresidioPDFApp:
    """PDF個人情報マスキングツールのメインアプリケーション"""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "PDF個人情報マスキングツール"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 0
        
        # PDFビューア
        self.pdf_viewer = PDFViewer()
        
        # アプリケーション状態
        self.current_pdf_path: Optional[str] = None
        self.detection_results: List[Dict] = []
        self.current_page_index = 0
        self.zoom_level = 1.0
        self.selected_entity = None
        
        # UIコンポーネント
        self.status_text = ft.Text("準備完了", size=12)
        self.progress_bar = ft.ProgressBar(visible=False)
        self.page_info_text = ft.Text("ページ -/-", size=12)
        self.zoom_info_text = ft.Text("ズーム: 100%", size=12)
        
        # PDFビューア領域
        self.pdf_image = ft.Image(
            src="",
            width=600,
            height=800,
            fit=ft.ImageFit.CONTAIN,
            border_radius=8
        )
        
        self.pdf_viewer_content = ft.Container(
            content=ft.Column([
                ft.Text("PDFファイルを選択してください", 
                       text_align=ft.TextAlign.CENTER,
                       size=16),
                ft.Text("📄", size=64, text_align=ft.TextAlign.CENTER)
            ], 
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER),
            expand=True,
            border_radius=8,
            padding=20
        )
        
        self.thumbnails_list = ft.ListView(expand=True, spacing=5)
        self.results_list = ft.ListView(expand=True, spacing=2)
        self.properties_panel = self._create_properties_panel()
        
        self._build_ui()
    
    def _build_ui(self):
        """UIを構築"""
        # ツールバー
        toolbar = ft.Row([
            ft.ElevatedButton("📁 ファイルを開く", on_click=self._open_file_dialog),
            ft.ElevatedButton("🔍 検出開始", on_click=self._start_detection),
            ft.ElevatedButton("💾 保存", on_click=self._save_masked_pdf),
            ft.ElevatedButton("⚙️ 設定", on_click=self._open_settings),
        ])
        
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
                    width=150,
                    padding=10
                ),
                
                # 中央パネル：PDFビューア
                ft.Container(
                    content=ft.Column([
                        # ナビゲーションツールバー
                        ft.Row([
                            ft.ElevatedButton("🔍+", on_click=self._zoom_in),
                            ft.ElevatedButton("🔍-", on_click=self._zoom_out),
                            self.zoom_info_text,
                            ft.Text("   "),  # スペーサー
                            ft.ElevatedButton("◀", on_click=self._previous_page),
                            self.page_info_text,
                            ft.ElevatedButton("▶", on_click=self._next_page),
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Divider(height=1),
                        # PDFビューア領域
                        ft.Container(
                            content=self.pdf_viewer_content,
                            expand=True,
                            border_radius=8
                        )
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
                            border_radius=4
                        ),
                        ft.Divider(height=10),
                        # プロパティパネル
                        ft.Text("プロパティ", weight=ft.FontWeight.BOLD, size=14),
                        ft.Divider(height=1),
                        self.properties_panel
                    ]),
                    width=280,
                    padding=10
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
            padding=ft.padding.symmetric(horizontal=20, vertical=8)
        )
        
        # ページにコンテンツを追加
        self.page.add(
            ft.Column([
                toolbar,
                ft.Divider(height=1),
                main_content,
                bottom_bar
            ], expand=True, spacing=0)
        )
        
        # ファイルピッカーを追加
        self.file_picker = ft.FilePicker(on_result=self._file_picker_result)
        self.page.overlay.append(self.file_picker)
        self.page.update()
    
    def _create_properties_panel(self) -> ft.Container:
        """プロパティパネルを作成"""
        return ft.Container(
            content=ft.Column([
                ft.Text("エンティティが選択されていません", size=12),
            ]),
            height=200,
            border_radius=4,
            padding=10
        )
    
    # ===== イベントハンドラー =====
    
    def _open_file_dialog(self, e):
        """ファイル選択ダイアログを開く"""
        self.file_picker.pick_files(
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
            
            # PDFビューアでファイルを読み込み
            if self.pdf_viewer.load_pdf(file_path):
                self._update_pdf_display()
                self._update_thumbnails()
                
                filename = os.path.basename(file_path)
                self.status_text.value = f"PDFファイル読み込み完了: {filename}"
                
                # ページ情報を更新
                self._update_page_info()
                
            else:
                # PyMuPDFが利用できない場合の代替表示
                filename = os.path.basename(file_path)
                self.pdf_viewer_content.content = ft.Column([
                    ft.Text(f"読み込み済み: {filename}", size=16, weight=ft.FontWeight.BOLD),
                    ft.Text(f"パス: {file_path}", size=12),
                    ft.Container(
                        content=ft.Text("PDF表示にはPyMuPDFが必要です", 
                                       text_align=ft.TextAlign.CENTER),
                        height=400,
                        border_radius=8,
                        padding=20
                    )
                ])
                self.status_text.value = f"PDFファイル読み込み完了（表示制限あり）: {filename}"
            
            self.page.update()
            
        except Exception as ex:
            self._show_error(f"PDFファイルの読み込みに失敗しました: {str(ex)}")
    
    def _update_pdf_display(self):
        """PDFページ表示を更新"""
        if not self.pdf_viewer.document:
            return
        
        # 現在のページを画像として描画
        img_data = self.pdf_viewer.render_page(self.current_page_index, self.zoom_level)
        
        if img_data:
            self.pdf_image.src = img_data
            self.pdf_viewer_content.content = ft.Container(
                content=self.pdf_image,
                alignment=ft.alignment.center,
                expand=True
            )
        else:
            self.pdf_viewer_content.content = ft.Text(
                "ページの表示に失敗しました",
                text_align=ft.TextAlign.CENTER
            )
        
        self.page.update()
    
    def _update_thumbnails(self):
        """サムネイル一覧を更新"""
        self.thumbnails_list.controls.clear()
        
        if not self.pdf_viewer.document:
            return
        
        page_count = self.pdf_viewer.get_page_count()
        
        for i in range(page_count):
            thumbnail_data = self.pdf_viewer.render_thumbnail(i, width=100)
            
            if thumbnail_data:
                thumbnail_img = ft.Image(
                    src=thumbnail_data,
                    width=100,
                    height=130,
                    fit=ft.ImageFit.CONTAIN,
                    border_radius=4
                )
            else:
                thumbnail_img = ft.Container(
                    content=ft.Text(f"P.{i+1}", text_align=ft.TextAlign.CENTER),
                    width=100,
                    height=130,
                    border_radius=4
                )
            
            thumbnail = ft.Container(
                content=ft.Column([
                    thumbnail_img,
                    ft.Text(f"ページ {i+1}", size=10, text_align=ft.TextAlign.CENTER)
                ]),
                on_click=lambda e, page_idx=i: self._jump_to_page(page_idx),
                border_radius=4,
                padding=5
            )
            self.thumbnails_list.controls.append(thumbnail)
        
        self.page.update()    
    def _update_page_info(self):
        """ページ情報を更新"""
        if self.pdf_viewer.document:
            page_count = self.pdf_viewer.get_page_count()
            self.page_info_text.value = f"ページ {self.current_page_index + 1}/{page_count}"
        else:
            self.page_info_text.value = "ページ -/-"
        
        self.zoom_info_text.value = f"ズーム: {int(self.zoom_level * 100)}%"
        self.page.update()
    
    def _zoom_in(self, e):
        """ズームイン"""
        self.zoom_level = min(self.zoom_level * 1.25, 5.0)
        self._update_pdf_display()
        self._update_page_info()
    
    def _zoom_out(self, e):
        """ズームアウト"""
        self.zoom_level = max(self.zoom_level / 1.25, 0.25)
        self._update_pdf_display()
        self._update_page_info()
    
    def _previous_page(self, e):
        """前のページに移動"""
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self._update_pdf_display()
            self._update_page_info()
            self._update_thumbnails()
    
    def _next_page(self, e):
        """次のページに移動"""
        if self.pdf_viewer.document:
            page_count = self.pdf_viewer.get_page_count()
            if self.current_page_index < page_count - 1:
                self.current_page_index += 1
                self._update_pdf_display()
                self._update_page_info()
                self._update_thumbnails()
    
    def _jump_to_page(self, page_index: int):
        """指定ページにジャンプ"""
        if self.pdf_viewer.document:
            page_count = self.pdf_viewer.get_page_count()
            if 0 <= page_index < page_count:
                self.current_page_index = page_index
                self._update_pdf_display()
                self._update_page_info()
                self._update_thumbnails()
    
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
            
            # 模擬的な検出結果
            await asyncio.sleep(2)  # 処理中を模擬
            
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
                    "page": 1,
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
            self.status_text.value = f"個人情報検出完了: {len(self.detection_results)}件の検出"
            
        except Exception as ex:
            self._show_error(f"検出処理中にエラーが発生しました: {str(ex)}")
        
        finally:
            # プログレスバー非表示
            self.progress_bar.visible = False
            self.page.update()
    
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
            ft.Text("選択されたエンティティ", size=12, weight=ft.FontWeight.BOLD),
            ft.Divider(height=10),
            ft.Row([
                ft.Text("タイプ:", weight=ft.FontWeight.BOLD),
                ft.Text(entity_type_jp)
            ]),
            ft.Row([
                ft.Text("テキスト:", weight=ft.FontWeight.BOLD),
                ft.Text(entity["text"], expand=True)
            ]),
            ft.Row([
                ft.Text("信頼度:", weight=ft.FontWeight.BOLD),
                ft.Text(f"{entity['confidence']:.3f}")
            ]),
            ft.Row([
                ft.Text("ページ:", weight=ft.FontWeight.BOLD),
                ft.Text(str(entity["page"]))
            ]),
            ft.Divider(height=10),
            ft.ElevatedButton(
                "🗑️ アノテーション削除",
                on_click=self._delete_annotation
            )
        ])
        
        self.page.update()
    
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
                ft.Text("エンティティが選択されていません", size=12)
            ])
            self.page.update()
    
    def _save_masked_pdf(self, e):
        """マスキング済みPDFを保存"""
        if not self.current_pdf_path:
            self._show_error("PDFファイルが選択されていません")
            return
        
        self.status_text.value = "マスキング済みPDF保存機能は開発中です"
        self.page.update()
    
    def _open_settings(self, e):
        """設定画面を開く"""
        # 簡単な設定ダイアログ
        def close_settings(e):
            settings_dialog.open = False
            self.page.update()
        
        settings_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("設定"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("検出対象エンティティ", weight=ft.FontWeight.BOLD),
                    ft.Checkbox(label="人名 (PERSON)", value=True),
                    ft.Checkbox(label="場所 (LOCATION)", value=True),
                    ft.Checkbox(label="電話番号 (PHONE_NUMBER)", value=True),
                    ft.Checkbox(label="日時 (DATE_TIME)", value=True),
                    ft.Divider(),
                    ft.Text("信頼度閾値", weight=ft.FontWeight.BOLD),
                    ft.Slider(min=0.0, max=1.0, value=0.5, divisions=10),
                ], tight=True),
                width=300,
                height=300
            ),
            actions=[
                ft.TextButton("キャンセル", on_click=close_settings),
                ft.TextButton("保存", on_click=close_settings)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        self.page.dialog = settings_dialog
        settings_dialog.open = True
        self.page.update()
    
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


def main(page: ft.Page):
    """メイン関数"""
    print("PDF個人情報マスキングツール起動中...")
    
    # ページ設定
    page.window_width = 1400
    page.window_height = 900
    page.window_min_width = 1000
    page.window_min_height = 700
    
    # アプリケーションを作成
    app = PresidioPDFApp(page)
    
    print("アプリケーション初期化完了")


if __name__ == "__main__":
    # Fletアプリケーションを起動
    print("Fletアプリケーション開始...")
    ft.app(target=main, name="PDF個人情報マスキングツール", port=8892)