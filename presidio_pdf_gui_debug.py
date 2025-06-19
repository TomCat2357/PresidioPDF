#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - FletによるGUI実装（デバッグ版）
"""

import flet as ft
import os
import json
import subprocess
import asyncio
import base64
import io
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('presidio_pdf_gui.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
    logger.info("PyMuPDF利用可能")
except ImportError as e:
    PYMUPDF_AVAILABLE = False
    logger.error(f"PyMuPDFが利用できません: {e}")


class PDFViewer:
    """PDFビューアクラス"""
    
    def __init__(self):
        self.document = None
        self.current_page = 0
        self.zoom_level = 1.0
        self.page_images = []
        logger.info("PDFViewer初期化完了")
    
    def load_pdf(self, file_path: str) -> bool:
        """PDFファイルを読み込み"""
        logger.info(f"PDFファイル読み込み開始: {file_path}")
        
        if not PYMUPDF_AVAILABLE:
            logger.error("PyMuPDFが利用できないため、PDF読み込みに失敗")
            return False
        
        try:
            # ファイル存在確認
            if not os.path.exists(file_path):
                logger.error(f"ファイルが存在しません: {file_path}")
                return False
            
            logger.info(f"PyMuPDFでファイルを開いています: {file_path}")
            self.document = fitz.open(file_path)
            self.current_page = 0
            self.page_images.clear()
            
            page_count = len(self.document)
            logger.info(f"PDF読み込み成功: {page_count}ページ")
            return True
            
        except Exception as e:
            logger.error(f"PDF読み込みエラー: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def get_page_count(self) -> int:
        """総ページ数を取得"""
        if self.document:
            count = len(self.document)
            logger.debug(f"総ページ数: {count}")
            return count
        return 0
    
    def render_page(self, page_num: int, zoom: float = 1.0) -> Optional[str]:
        """指定ページを画像として描画し、base64エンコードされた文字列を返す"""
        logger.debug(f"ページ描画開始: ページ{page_num+1}, ズーム{zoom}")
        
        if not self.document or page_num >= len(self.document):
            logger.error(f"無効なページ番号: {page_num}")
            return None
        
        try:
            page = self.document[page_num]
            logger.debug(f"ページオブジェクト取得成功: {page}")
            
            # 解像度を設定（zoom倍率を適用）
            matrix = fitz.Matrix(zoom, zoom)
            logger.debug(f"変換マトリックス作成: {matrix}")
            
            pix = page.get_pixmap(matrix=matrix)
            logger.debug(f"ピクスマップ作成成功: {pix.width}x{pix.height}")
            
            # PNG形式でバイト配列に変換
            img_data = pix.tobytes("png")
            logger.debug(f"PNG変換完了: {len(img_data)}バイト")
            
            # base64エンコード
            img_base64 = base64.b64encode(img_data).decode()
            logger.debug(f"base64エンコード完了: {len(img_base64)}文字")
            
            result = f"data:image/png;base64,{img_base64}"
            logger.info(f"ページ{page_num+1}の描画完了")
            return result
            
        except Exception as e:
            logger.error(f"ページ描画エラー: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def render_thumbnail(self, page_num: int, width: int = 100) -> Optional[str]:
        """サムネイルを生成"""
        logger.debug(f"サムネイル生成開始: ページ{page_num+1}, 幅{width}")
        
        if not self.document or page_num >= len(self.document):
            logger.error(f"無効なページ番号（サムネイル）: {page_num}")
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
            
            result = f"data:image/png;base64,{img_base64}"
            logger.debug(f"サムネイル生成完了: ページ{page_num+1}")
            return result
            
        except Exception as e:
            logger.error(f"サムネイル生成エラー: {e}")
            logger.error(traceback.format_exc())
            return None


class PresidioPDFApp:
    """PDF個人情報マスキングツールのメインアプリケーション"""
    
    def __init__(self, page: ft.Page):
        logger.info("PresidioPDFApp初期化開始")
        
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
        
        # ログ表示エリア
        self.log_text = ft.Text("", size=10, selectable=True)
        self.log_container = ft.Container(
            content=ft.Column([
                ft.Text("ログ", weight=ft.FontWeight.BOLD, size=12),
                ft.Container(
                    content=self.log_text,
                    height=100,
                    border_radius=4,
                    padding=5,
                    scroll=ft.ScrollMode.AUTO
                )
            ]),
            height=150,
            visible=False
        )
        
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
        
        try:
            self._build_ui()
            logger.info("PresidioPDFApp初期化完了")
        except Exception as e:
            logger.error(f"UI構築中にエラー: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _log_to_ui(self, message: str):
        """UIにログメッセージを追加"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        
        # ログテキストに追加（最大100行に制限）
        current_text = self.log_text.value
        lines = current_text.split('\n')
        if len(lines) > 100:
            lines = lines[-100:]
        
        lines.append(log_line.strip())
        self.log_text.value = '\n'.join(lines)
        
        if hasattr(self, 'page'):
            try:
                self.page.update()
            except Exception as e:
                logger.error(f"ログUI更新エラー: {e}")
    
    def _build_ui(self):
        """UIを構築"""
        logger.info("UI構築開始")
        
        # ツールバー
        toolbar = ft.Row([
            ft.ElevatedButton("📁 ファイルを開く", on_click=self._open_file_dialog),
            ft.ElevatedButton("🔍 検出開始", on_click=self._start_detection),
            ft.ElevatedButton("💾 保存", on_click=self._save_masked_pdf),
            ft.ElevatedButton("⚙️ 設定", on_click=self._open_settings),
            ft.ElevatedButton("📝 ログ表示", on_click=self._toggle_log),
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
        
        # ボトムエリア（ステータスバー + ログ）
        bottom_area = ft.Column([
            # ステータスバー
            ft.Container(
                content=ft.Row([
                    self.status_text,
                    ft.Container(expand=True),  # スペーサー
                    self.progress_bar
                ]),
                padding=ft.padding.symmetric(horizontal=20, vertical=8)
            ),
            # ログエリア（非表示）
            self.log_container
        ])
        
        # ページにコンテンツを追加
        self.page.add(
            ft.Column([
                toolbar,
                ft.Divider(height=1),
                main_content,
                bottom_area
            ], expand=True, spacing=0)
        )
        
        # ファイルピッカーを追加
        self.file_picker = ft.FilePicker(on_result=self._file_picker_result)
        self.page.overlay.append(self.file_picker)
        self.page.update()
        
        logger.info("UI構築完了")
        self._log_to_ui("UI構築完了")    
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
    
    def _toggle_log(self, e):
        """ログ表示の切り替え"""
        self.log_container.visible = not self.log_container.visible
        self.page.update()
        logger.info(f"ログ表示切り替え: {self.log_container.visible}")
    
    # ===== イベントハンドラー =====
    
    def _open_file_dialog(self, e):
        """ファイル選択ダイアログを開く"""
        logger.info("ファイル選択ダイアログを開く")
        self._log_to_ui("ファイル選択ダイアログを開いています...")
        
        try:
            self.file_picker.pick_files(
                dialog_title="PDFファイルを選択",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf"],
                allow_multiple=False
            )
        except Exception as e:
            logger.error(f"ファイル選択ダイアログエラー: {e}")
            self._log_to_ui(f"ファイル選択エラー: {e}")
    
    def _file_picker_result(self, e: ft.FilePickerResultEvent):
        """ファイル選択結果の処理"""
        logger.info("ファイル選択結果処理開始")
        
        try:
            if e.files:
                file_path = e.files[0].path
                logger.info(f"選択されたファイル: {file_path}")
                self._log_to_ui(f"ファイルが選択されました: {os.path.basename(file_path)}")
                self._load_pdf_file(file_path)
            else:
                logger.info("ファイル選択がキャンセルされました")
                self._log_to_ui("ファイル選択がキャンセルされました")
        except Exception as ex:
            logger.error(f"ファイル選択結果処理エラー: {ex}")
            logger.error(traceback.format_exc())
            self._log_to_ui(f"ファイル選択処理エラー: {ex}")
    
    def _load_pdf_file(self, file_path: str):
        """PDFファイルを読み込み"""
        logger.info(f"PDFファイル読み込み開始: {file_path}")
        self._log_to_ui(f"PDFファイル読み込み中: {os.path.basename(file_path)}")
        
        try:
            self.current_pdf_path = file_path
            self.current_page_index = 0
            
            # ファイルサイズチェック
            file_size = os.path.getsize(file_path)
            logger.info(f"ファイルサイズ: {file_size} bytes")
            self._log_to_ui(f"ファイルサイズ: {file_size:,} bytes")
            
            # PDFビューアでファイルを読み込み
            if self.pdf_viewer.load_pdf(file_path):
                logger.info("PDF読み込み成功、表示更新開始")
                self._log_to_ui("PDF読み込み成功、表示更新中...")
                
                # 表示更新（安全に実行）
                try:
                    self._update_pdf_display()
                    self._log_to_ui("PDFページ表示完了")
                except Exception as display_error:
                    logger.error(f"PDF表示更新エラー: {display_error}")
                    self._log_to_ui(f"PDF表示エラー: {display_error}")
                
                try:
                    self._update_thumbnails()
                    self._log_to_ui("サムネイル生成完了")
                except Exception as thumb_error:
                    logger.error(f"サムネイル更新エラー: {thumb_error}")
                    self._log_to_ui(f"サムネイル生成エラー: {thumb_error}")
                
                filename = os.path.basename(file_path)
                self.status_text.value = f"PDFファイル読み込み完了: {filename}"
                
                # ページ情報を更新
                self._update_page_info()
                
            else:
                # PyMuPDFが利用できない場合の代替表示
                logger.warning("PyMuPDF利用不可、代替表示モード")
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
                self._log_to_ui("PyMuPDF未対応のため、代替表示モードで動作中")
            
            self.page.update()
            logger.info("PDFファイル読み込み処理完了")
            
        except Exception as ex:
            logger.error(f"PDFファイル読み込みエラー: {ex}")
            logger.error(traceback.format_exc())
            self._log_to_ui(f"PDFファイル読み込みエラー: {ex}")
            self._show_error(f"PDFファイルの読み込みに失敗しました: {str(ex)}")
    
    def _update_pdf_display(self):
        """PDFページ表示を更新"""
        logger.debug("PDF表示更新開始")
        
        if not self.pdf_viewer.document:
            logger.warning("PDFドキュメントが読み込まれていません")
            return
        
        try:
            # 現在のページを画像として描画
            logger.debug(f"ページ{self.current_page_index + 1}を描画中...")
            img_data = self.pdf_viewer.render_page(self.current_page_index, self.zoom_level)
            
            if img_data:
                logger.debug("画像データ取得成功、UI更新中...")
                self.pdf_image.src = img_data
                self.pdf_viewer_content.content = ft.Container(
                    content=self.pdf_image,
                    alignment=ft.alignment.center,
                    expand=True
                )
                logger.info(f"ページ{self.current_page_index + 1}の表示更新完了")
            else:
                logger.error("画像データの取得に失敗")
                self.pdf_viewer_content.content = ft.Text(
                    "ページの表示に失敗しました",
                    text_align=ft.TextAlign.CENTER
                )
            
            self.page.update()
            
        except Exception as e:
            logger.error(f"PDF表示更新エラー: {e}")
            logger.error(traceback.format_exc())
            self._log_to_ui(f"PDF表示更新エラー: {e}")
    
    def _update_thumbnails(self):
        """サムネイル一覧を更新"""
        logger.debug("サムネイル更新開始")
        
        try:
            self.thumbnails_list.controls.clear()
            
            if not self.pdf_viewer.document:
                logger.warning("PDFドキュメントが読み込まれていません（サムネイル）")
                return
            
            page_count = self.pdf_viewer.get_page_count()
            logger.info(f"{page_count}ページのサムネイルを生成中...")
            
            for i in range(min(page_count, 10)):  # 最大10ページまでに制限
                try:
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
                    
                except Exception as thumb_error:
                    logger.error(f"ページ{i+1}のサムネイル生成エラー: {thumb_error}")
                    continue
            
            self.page.update()
            logger.info("サムネイル更新完了")
            
        except Exception as e:
            logger.error(f"サムネイル更新エラー: {e}")
            logger.error(traceback.format_exc())
            self._log_to_ui(f"サムネイル更新エラー: {e}")
    
    def _update_page_info(self):
        """ページ情報を更新"""
        try:
            if self.pdf_viewer.document:
                page_count = self.pdf_viewer.get_page_count()
                self.page_info_text.value = f"ページ {self.current_page_index + 1}/{page_count}"
            else:
                self.page_info_text.value = "ページ -/-"
            
            self.zoom_info_text.value = f"ズーム: {int(self.zoom_level * 100)}%"
            self.page.update()
        except Exception as e:
            logger.error(f"ページ情報更新エラー: {e}")
    
    def _zoom_in(self, e):
        """ズームイン"""
        try:
            self.zoom_level = min(self.zoom_level * 1.25, 5.0)
            logger.info(f"ズームイン: {self.zoom_level}")
            self._log_to_ui(f"ズーム: {int(self.zoom_level * 100)}%")
            self._update_pdf_display()
            self._update_page_info()
        except Exception as ex:
            logger.error(f"ズームインエラー: {ex}")
    
    def _zoom_out(self, e):
        """ズームアウト"""
        try:
            self.zoom_level = max(self.zoom_level / 1.25, 0.25)
            logger.info(f"ズームアウト: {self.zoom_level}")
            self._log_to_ui(f"ズーム: {int(self.zoom_level * 100)}%")
            self._update_pdf_display()
            self._update_page_info()
        except Exception as ex:
            logger.error(f"ズームアウトエラー: {ex}")
    
    def _previous_page(self, e):
        """前のページに移動"""
        try:
            if self.current_page_index > 0:
                self.current_page_index -= 1
                logger.info(f"前のページ: {self.current_page_index + 1}")
                self._log_to_ui(f"ページ {self.current_page_index + 1} に移動")
                self._update_pdf_display()
                self._update_page_info()
        except Exception as ex:
            logger.error(f"前ページ移動エラー: {ex}")
    
    def _next_page(self, e):
        """次のページに移動"""
        try:
            if self.pdf_viewer.document:
                page_count = self.pdf_viewer.get_page_count()
                if self.current_page_index < page_count - 1:
                    self.current_page_index += 1
                    logger.info(f"次のページ: {self.current_page_index + 1}")
                    self._log_to_ui(f"ページ {self.current_page_index + 1} に移動")
                    self._update_pdf_display()
                    self._update_page_info()
        except Exception as ex:
            logger.error(f"次ページ移動エラー: {ex}")
    
    def _jump_to_page(self, page_index: int):
        """指定ページにジャンプ"""
        try:
            if self.pdf_viewer.document:
                page_count = self.pdf_viewer.get_page_count()
                if 0 <= page_index < page_count:
                    self.current_page_index = page_index
                    logger.info(f"ページジャンプ: {self.current_page_index + 1}")
                    self._log_to_ui(f"ページ {self.current_page_index + 1} にジャンプ")
                    self._update_pdf_display()
                    self._update_page_info()
        except Exception as ex:
            logger.error(f"ページジャンプエラー: {ex}")
    
    def _start_detection(self, e):
        """個人情報検出を開始"""
        logger.info("個人情報検出開始")
        self._log_to_ui("個人情報検出を開始しています...")
        
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
            self._log_to_ui("検出処理中（模擬データ）...")
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
                }
            ]
            
            # 検出結果一覧を更新
            self._update_results_list()
            self.status_text.value = f"個人情報検出完了: {len(self.detection_results)}件の検出"
            self._log_to_ui(f"検出完了: {len(self.detection_results)}件")
            
        except Exception as ex:
            logger.error(f"検出処理エラー: {ex}")
            self._log_to_ui(f"検出処理エラー: {ex}")
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
        try:
            if 0 <= index < len(self.detection_results):
                self.selected_entity = self.detection_results[index]
                self._update_properties_panel()
                logger.info(f"エンティティ選択: {self.selected_entity['text']}")
        except Exception as ex:
            logger.error(f"エンティティ選択エラー: {ex}")
    
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
            ft.ElevatedButton(
                "🗑️ アノテーション削除",
                on_click=self._delete_annotation
            )
        ])
        
        self.page.update()
    
    def _delete_annotation(self, e):
        """アノテーションを削除"""
        try:
            if self.selected_entity:
                if self.selected_entity in self.detection_results:
                    self.detection_results.remove(self.selected_entity)
                
                self.selected_entity = None
                self._update_results_list()
                self.properties_panel.content = ft.Column([
                    ft.Text("エンティティが選択されていません", size=12)
                ])
                self.page.update()
                logger.info("アノテーション削除完了")
        except Exception as ex:
            logger.error(f"アノテーション削除エラー: {ex}")
    
    def _save_masked_pdf(self, e):
        """マスキング済みPDFを保存"""
        self._log_to_ui("保存機能は開発中です")
        
    def _open_settings(self, e):
        """設定画面を開く"""
        self._log_to_ui("設定画面は開発中です")
    
    def _show_error(self, message: str):
        """エラーメッセージを表示"""
        try:
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
        except Exception as ex:
            logger.error(f"エラーダイアログ表示エラー: {ex}")
    
    def _close_dialog(self, dialog):
        """ダイアログを閉じる"""
        try:
            dialog.open = False
            self.page.update()
        except Exception as ex:
            logger.error(f"ダイアログクローズエラー: {ex}")


def main(page: ft.Page):
    """メイン関数"""
    logger.info("メイン関数開始")
    print("PDF個人情報マスキングツール起動中...")
    
    try:
        # ページ設定
        page.window_width = 1400
        page.window_height = 900
        page.window_min_width = 1000
        page.window_min_height = 700
        
        # アプリケーションを作成
        app = PresidioPDFApp(page)
        
        logger.info("アプリケーション初期化完了")
        print("アプリケーション初期化完了")
        
    except Exception as e:
        logger.error(f"メイン関数エラー: {e}")
        logger.error(traceback.format_exc())
        print(f"アプリケーション初期化エラー: {e}")
        raise


if __name__ == "__main__":
    # Fletアプリケーションを起動
    logger.info("Fletアプリケーション開始")
    print("Fletアプリケーション開始...")
    
    try:
        ft.app(target=main, name="PDF個人情報マスキングツール", port=8893)
    except Exception as e:
        logger.error(f"Fletアプリ起動エラー: {e}")
        print(f"Fletアプリ起動エラー: {e}")
        raise