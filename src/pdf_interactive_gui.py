#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
インタラクティブPDF編集GUI
ハイライトのクリック検出と範囲調整機能付きGUI
"""

import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import threading
import io
from typing import Optional, List
from pathlib import Path

from interactive_pdf_editor import InteractivePDFEditor, HighlightRegion, EditMode

logger = logging.getLogger(__name__)

class PDFInteractiveGUI:
    """インタラクティブPDF編集GUI"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF インタラクティブ編集ツール")
        self.root.geometry("1200x800")
        
        self.editor: Optional[InteractivePDFEditor] = None
        self.current_page = 0
        self.zoom_factor = 1.0
        self.pdf_images: List[ImageTk.PhotoImage] = []
        
        self._setup_ui()
        self._setup_bindings()
    
    def _setup_ui(self):
        """UI要素を設定"""
        # メインフレーム
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ツールバー
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        # ファイル操作ボタン
        ttk.Button(toolbar, text="PDFを開く", command=self._open_pdf).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="保存", command=self._save_pdf).pack(side=tk.LEFT, padx=(0, 5))
        
        # 区切り線
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # ページナビゲーション
        ttk.Label(toolbar, text="ページ:").pack(side=tk.LEFT, padx=(0, 2))
        self.page_var = tk.IntVar(value=1)
        self.page_spinbox = ttk.Spinbox(toolbar, from_=1, to=1, width=5, textvariable=self.page_var, command=self._on_page_change)
        self.page_spinbox.pack(side=tk.LEFT, padx=(0, 5))
        self.page_label = ttk.Label(toolbar, text="/ 1")
        self.page_label.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(toolbar, text="◀", command=self._prev_page).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(toolbar, text="▶", command=self._next_page).pack(side=tk.LEFT, padx=(0, 5))
        
        # 区切り線
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # ズーム操作
        ttk.Label(toolbar, text="ズーム:").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(toolbar, text="-", command=self._zoom_out).pack(side=tk.LEFT)
        self.zoom_label = ttk.Label(toolbar, text="100%", width=6)
        self.zoom_label.pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="+", command=self._zoom_in).pack(side=tk.LEFT, padx=(0, 5))
        
        # 区切り線
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # 編集モード
        ttk.Label(toolbar, text="編集モード:").pack(side=tk.LEFT, padx=(0, 2))
        self.edit_mode_var = tk.StringVar(value="select")
        edit_mode_combo = ttk.Combobox(toolbar, textvariable=self.edit_mode_var, values=[
            "select", "extend_left", "extend_right", "shrink_left", "shrink_right"
        ], state="readonly", width=12)
        edit_mode_combo.pack(side=tk.LEFT, padx=(0, 5))
        edit_mode_combo.bind("<<ComboboxSelected>>", self._on_edit_mode_change)
        
        # 区切り線
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # ハイライト調整ボタン
        ttk.Button(toolbar, text="← 拡張", command=lambda: self._adjust_highlight("left")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(toolbar, text="拡張 →", command=lambda: self._adjust_highlight("right")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(toolbar, text="← 縮小", command=lambda: self._adjust_highlight("shrink_left")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(toolbar, text="縮小 →", command=lambda: self._adjust_highlight("shrink_right")).pack(side=tk.LEFT, padx=(0, 5))
        
        # メインコンテンツエリア
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左パネル: PDFビューア
        pdf_frame = ttk.LabelFrame(content_frame, text="PDF ビューア", padding=5)
        pdf_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # スクロール可能なPDFキャンバス
        canvas_frame = ttk.Frame(pdf_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.pdf_canvas = tk.Canvas(canvas_frame, bg="white")
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.pdf_canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.pdf_canvas.xview)
        
        self.pdf_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.pdf_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 右パネル: ハイライト情報
        info_frame = ttk.LabelFrame(content_frame, text="ハイライト情報", padding=5, width=300)
        info_frame.pack(side=tk.RIGHT, fill=tk.Y)
        info_frame.pack_propagate(False)  # サイズ固定
        
        # 選択されたハイライト情報
        selection_frame = ttk.LabelFrame(info_frame, text="選択中のハイライト", padding=5)
        selection_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.selected_info = tk.Text(selection_frame, height=8, wrap=tk.WORD)
        self.selected_info.pack(fill=tk.BOTH, expand=True)
        
        # ハイライト一覧
        list_frame = ttk.LabelFrame(info_frame, text="すべてのハイライト", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # ハイライトリスト
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        self.highlight_tree = ttk.Treeview(list_container, columns=("type", "text"), show="headings", height=15)
        self.highlight_tree.heading("type", text="タイプ")
        self.highlight_tree.heading("text", text="テキスト")
        
        self.highlight_tree.column("type", width=80)
        self.highlight_tree.column("text", width=150)
        
        list_scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.highlight_tree.yview)
        self.highlight_tree.configure(yscrollcommand=list_scrollbar.set)
        
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.highlight_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # ステータスバー
        self.status_var = tk.StringVar(value="PDFファイルを開いてください")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, pady=(5, 0))
    
    def _setup_bindings(self):
        """イベントバインディングを設定"""
        self.pdf_canvas.bind("<Button-1>", self._on_canvas_click)
        self.highlight_tree.bind("<<TreeviewSelect>>", self._on_highlight_select)
        
        # キーボードショートカット
        self.root.bind("<Control-o>", lambda e: self._open_pdf())
        self.root.bind("<Control-s>", lambda e: self._save_pdf())
        self.root.bind("<Left>", lambda e: self._prev_page())
        self.root.bind("<Right>", lambda e: self._next_page())
        self.root.bind("<Control-equal>", lambda e: self._zoom_in())
        self.root.bind("<Control-minus>", lambda e: self._zoom_out())
    
    def _open_pdf(self):
        """PDFファイルを開く"""
        file_path = filedialog.askopenfilename(
            title="PDFファイルを選択",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.status_var.set("PDFを読み込み中...")
                self.root.update()
                
                # 既存のエディターを閉じる
                if self.editor:
                    self.editor.close()
                
                # 新しいエディターを作成
                self.editor = InteractivePDFEditor(file_path)
                self.editor.on_highlight_changed = self._on_highlight_changed
                
                # ページ数を更新
                page_count = len(self.editor.doc)
                self.page_spinbox.configure(to=page_count)
                self.page_label.configure(text=f"/ {page_count}")
                
                # 最初のページを表示
                self.current_page = 0
                self.page_var.set(1)
                self._render_current_page()
                self._update_highlight_list()
                
                self.status_var.set(f"PDFを読み込みました: {Path(file_path).name}")
                
            except Exception as e:
                logger.error(f"PDFファイル読み込みエラー: {e}")
                messagebox.showerror("エラー", f"PDFファイルの読み込みに失敗しました: {e}")
                self.status_var.set("エラーが発生しました")
    
    def _save_pdf(self):
        """PDFファイルを保存"""
        if not self.editor:
            messagebox.showwarning("警告", "PDFファイルが開かれていません")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="PDFファイルを保存",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.status_var.set("PDFを保存中...")
                self.root.update()
                
                self.editor.save_changes(file_path)
                
                self.status_var.set(f"PDFを保存しました: {Path(file_path).name}")
                messagebox.showinfo("成功", "PDFファイルを保存しました")
                
            except Exception as e:
                logger.error(f"PDFファイル保存エラー: {e}")
                messagebox.showerror("エラー", f"PDFファイルの保存に失敗しました: {e}")
                self.status_var.set("保存に失敗しました")
    
    def _render_current_page(self):
        """現在のページをレンダリング"""
        if not self.editor:
            return
        
        try:
            page = self.editor.doc[self.current_page]
            
            # ページをイメージに変換
            matrix = fitz.Matrix(self.zoom_factor, self.zoom_factor)
            pix = page.get_pixmap(matrix=matrix)
            img_data = pix.tobytes("ppm")
            
            # PILイメージに変換
            img = Image.open(io.BytesIO(img_data))
            photo = ImageTk.PhotoImage(img)
            
            # キャンバスに表示
            self.pdf_canvas.delete("all")
            self.pdf_canvas.create_image(0, 0, anchor=tk.NW, image=photo, tags="pdf_page")
            
            # スクロール領域を更新
            self.pdf_canvas.configure(scrollregion=self.pdf_canvas.bbox("all"))
            
            # 画像参照を保持
            if len(self.pdf_images) <= self.current_page:
                self.pdf_images.extend([None] * (self.current_page + 1 - len(self.pdf_images)))
            self.pdf_images[self.current_page] = photo
            
        except Exception as e:
            logger.error(f"ページレンダリングエラー: {e}")
    
    def _on_canvas_click(self, event):
        """キャンバスクリックイベント"""
        if not self.editor:
            return
        
        # キャンバス座標をPDF座標に変換
        canvas_x = self.pdf_canvas.canvasx(event.x)
        canvas_y = self.pdf_canvas.canvasy(event.y)
        
        # ズーム補正
        pdf_x = canvas_x / self.zoom_factor
        pdf_y = canvas_y / self.zoom_factor
        
        point = fitz.Point(pdf_x, pdf_y)
        
        # ハイライトを選択
        if self.editor.select_highlight(self.current_page, point):
            self._update_selected_highlight_info()
            self.status_var.set("ハイライトを選択しました")
        else:
            self.editor.selected_highlight = None
            self._clear_selected_highlight_info()
            self.status_var.set("ハイライトが選択されていません")
    
    def _adjust_highlight(self, direction: str):
        """ハイライト範囲を調整"""
        if not self.editor or not self.editor.selected_highlight:
            messagebox.showwarning("警告", "ハイライトが選択されていません")
            return
        
        try:
            if self.editor.adjust_highlight_range(direction, 1):
                self._render_current_page()  # ページを再描画
                self._update_selected_highlight_info()
                self._update_highlight_list()
                self.status_var.set(f"ハイライト範囲を調整しました: {direction}")
            else:
                self.status_var.set("ハイライト範囲の調整に失敗しました")
                
        except Exception as e:
            logger.error(f"ハイライト調整エラー: {e}")
            messagebox.showerror("エラー", f"ハイライト調整に失敗しました: {e}")
    
    def _update_selected_highlight_info(self):
        """選択されたハイライト情報を更新"""
        if not self.editor or not self.editor.selected_highlight:
            self._clear_selected_highlight_info()
            return
        
        highlight = self.editor.selected_highlight
        info_text = f"""エンティティタイプ: {highlight.entity_type}
ページ: {highlight.page_num + 1}
テキスト: {highlight.text}

操作方法:
- ← 拡張: 左端を拡張
- 拡張 →: 右端を拡張  
- ← 縮小: 左端を縮小
- 縮小 →: 右端を縮小"""
        
        self.selected_info.delete(1.0, tk.END)
        self.selected_info.insert(1.0, info_text)
    
    def _clear_selected_highlight_info(self):
        """選択されたハイライト情報をクリア"""
        self.selected_info.delete(1.0, tk.END)
        self.selected_info.insert(1.0, "ハイライトが選択されていません")
    
    def _update_highlight_list(self):
        """ハイライト一覧を更新"""
        # 既存のアイテムを削除
        for item in self.highlight_tree.get_children():
            self.highlight_tree.delete(item)
        
        if not self.editor:
            return
        
        # ハイライト一覧を追加
        for i, highlight in enumerate(self.editor.highlights):
            self.highlight_tree.insert("", tk.END, values=(
                highlight.entity_type,
                highlight.text[:30] + "..." if len(highlight.text) > 30 else highlight.text
            ), tags=(str(i),))
    
    def _on_highlight_select(self, event):
        """ハイライト一覧の選択イベント"""
        selection = self.highlight_tree.selection()
        if selection and self.editor:
            item = self.highlight_tree.item(selection[0])
            highlight_index = int(item["tags"][0])
            
            if 0 <= highlight_index < len(self.editor.highlights):
                self.editor.selected_highlight = self.editor.highlights[highlight_index]
                
                # 該当ページに移動
                target_page = self.editor.selected_highlight.page_num
                if target_page != self.current_page:
                    self.current_page = target_page
                    self.page_var.set(target_page + 1)
                    self._render_current_page()
                
                self._update_selected_highlight_info()
    
    def _on_highlight_changed(self, highlight: HighlightRegion):
        """ハイライト変更時のコールバック"""
        self._update_highlight_list()
        self.status_var.set(f"ハイライトが変更されました: {highlight.entity_type}")
    
    def _prev_page(self):
        """前のページ"""
        if self.current_page > 0:
            self.current_page -= 1
            self.page_var.set(self.current_page + 1)
            self._render_current_page()
    
    def _next_page(self):
        """次のページ"""
        if self.editor and self.current_page < len(self.editor.doc) - 1:
            self.current_page += 1
            self.page_var.set(self.current_page + 1)
            self._render_current_page()
    
    def _on_page_change(self):
        """ページ変更"""
        try:
            new_page = self.page_var.get() - 1
            if self.editor and 0 <= new_page < len(self.editor.doc):
                self.current_page = new_page
                self._render_current_page()
        except tk.TclError:
            pass  # 無効な値の場合は無視
    
    def _zoom_in(self):
        """ズームイン"""
        self.zoom_factor = min(3.0, self.zoom_factor * 1.2)
        self._update_zoom_display()
        self._render_current_page()
    
    def _zoom_out(self):
        """ズームアウト"""
        self.zoom_factor = max(0.3, self.zoom_factor / 1.2)
        self._update_zoom_display()
        self._render_current_page()
    
    def _update_zoom_display(self):
        """ズーム表示を更新"""
        self.zoom_label.configure(text=f"{self.zoom_factor*100:.0f}%")
    
    def _on_edit_mode_change(self, event):
        """編集モード変更"""
        if self.editor:
            mode_map = {
                "select": EditMode.SELECT,
                "extend_left": EditMode.EXTEND_LEFT,
                "extend_right": EditMode.EXTEND_RIGHT,
                "shrink_left": EditMode.SHRINK_LEFT,
                "shrink_right": EditMode.SHRINK_RIGHT
            }
            mode = mode_map.get(self.edit_mode_var.get(), EditMode.SELECT)
            self.editor.set_edit_mode(mode)
    
    def run(self):
        """GUIを実行"""
        self.root.mainloop()
        
        # クリーンアップ
        if self.editor:
            self.editor.close()

def main():
    """メイン関数"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    root = tk.Tk()
    app = PDFInteractiveGUI(root)
    app.run()

if __name__ == "__main__":
    main()