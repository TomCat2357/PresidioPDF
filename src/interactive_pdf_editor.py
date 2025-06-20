#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
インタラクティブPDF編集機能
PyMuPDFを使用してハイライトのクリック検出と範囲調整を実装
"""

import logging
import fitz  # PyMuPDF
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class EditMode(Enum):
    """編集モード"""
    SELECT = "select"           # 選択モード
    EXTEND_LEFT = "extend_left"  # 左端拡張
    EXTEND_RIGHT = "extend_right"  # 右端拡張
    SHRINK_LEFT = "shrink_left"   # 左端縮小
    SHRINK_RIGHT = "shrink_right"  # 右端縮小

@dataclass
class HighlightRegion:
    """ハイライト領域情報"""
    page_num: int
    quad: fitz.Quad  # ハイライト座標
    annot: fitz.Annot  # 注釈オブジェクト
    entity_type: str   # エンティティタイプ
    confidence: float  # 信頼度
    text: str         # ハイライトされたテキスト
    original_start: int  # 元の開始位置
    original_end: int    # 元の終了位置

class InteractivePDFEditor:
    """インタラクティブPDF編集クラス"""
    
    def __init__(self, pdf_path: str):
        """
        Args:
            pdf_path: PDFファイルパス
        """
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.highlights: List[HighlightRegion] = []
        self.selected_highlight: Optional[HighlightRegion] = None
        self.edit_mode = EditMode.SELECT
        self.on_highlight_changed: Optional[Callable] = None
        
        self._load_existing_highlights()
    
    def _load_existing_highlights(self):
        """既存のハイライトを読み込み"""
        self.highlights.clear()
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            for annot in page.annots():
                if annot.type[1] == "Highlight":
                    # 注釈からメタデータを取得
                    content = annot.content or ""
                    entity_type = "UNKNOWN"
                    confidence = 0.0
                    
                    # コンテンツからエンティティタイプと信頼度を抽出
                    if ":" in content:
                        parts = content.split(":")
                        if len(parts) >= 2:
                            entity_type = parts[0].strip()
                            try:
                                confidence = float(parts[1].strip().replace("%", "")) / 100
                            except ValueError:
                                confidence = 0.0
                    
                    # ハイライトされたテキストを取得
                    quads = annot.vertices
                    if quads:
                        quad = fitz.Quad(quads[0])
                        text = page.get_textbox(quad).strip()
                        
                        highlight = HighlightRegion(
                            page_num=page_num,
                            quad=quad,
                            annot=annot,
                            entity_type=entity_type,
                            confidence=confidence,
                            text=text,
                            original_start=0,  # 後で計算
                            original_end=0     # 後で計算
                        )
                        self.highlights.append(highlight)
    
    def get_highlight_at_point(self, page_num: int, point: fitz.Point) -> Optional[HighlightRegion]:
        """指定座標のハイライトを取得"""
        page = self.doc[page_num]
        
        for highlight in self.highlights:
            if highlight.page_num == page_num:
                # ハイライト領域内かチェック
                if highlight.quad.contains(point):
                    return highlight
        
        return None
    
    def select_highlight(self, page_num: int, point: fitz.Point) -> bool:
        """ハイライトを選択"""
        highlight = self.get_highlight_at_point(page_num, point)
        
        if highlight:
            self.selected_highlight = highlight
            logger.info(f"ハイライトを選択: {highlight.entity_type} - {highlight.text}")
            return True
        else:
            self.selected_highlight = None
            return False
    
    def set_edit_mode(self, mode: EditMode):
        """編集モードを設定"""
        self.edit_mode = mode
        logger.debug(f"編集モードを変更: {mode.value}")
    
    def adjust_highlight_range(self, direction: str, amount: int = 1) -> bool:
        """
        ハイライト範囲を調整
        
        Args:
            direction: 調整方向 ("left", "right", "shrink_left", "shrink_right")
            amount: 調整する文字数
        
        Returns:
            bool: 調整成功かどうか
        """
        if not self.selected_highlight:
            logger.warning("ハイライトが選択されていません")
            return False
        
        highlight = self.selected_highlight
        page = self.doc[highlight.page_num]
        
        try:
            # 現在のテキスト範囲を取得
            current_text = highlight.text
            
            # ページの全テキストを取得
            page_text = page.get_text()
            
            # 現在のハイライトテキストの位置を特定
            text_start = page_text.find(current_text)
            if text_start == -1:
                logger.error("ハイライトテキストが見つかりません")
                return False
            
            text_end = text_start + len(current_text)
            
            # 範囲調整
            new_start = text_start
            new_end = text_end
            
            if direction == "left" and text_start > 0:
                # 左端を拡張
                new_start = max(0, text_start - amount)
            elif direction == "right" and text_end < len(page_text):
                # 右端を拡張
                new_end = min(len(page_text), text_end + amount)
            elif direction == "shrink_left" and text_end - text_start > amount:
                # 左端を縮小
                new_start = min(text_start + amount, text_end - 1)
            elif direction == "shrink_right" and text_end - text_start > amount:
                # 右端を縮小
                new_end = max(text_start + 1, text_end - amount)
            else:
                logger.warning(f"調整できません: direction={direction}, amount={amount}")
                return False
            
            # 新しいテキスト範囲
            new_text = page_text[new_start:new_end]
            
            # 新しい座標を計算
            new_quads = self._text_to_quads(page, new_start, new_end)
            if not new_quads:
                logger.error("新しい座標の計算に失敗")
                return False
            
            # ハイライトを更新
            self._update_highlight_annotation(highlight, new_quads, new_text)
            
            # ハイライト情報を更新
            highlight.quad = new_quads[0]
            highlight.text = new_text
            
            logger.info(f"ハイライト範囲を調整: '{current_text}' -> '{new_text}'")
            
            # コールバック呼び出し
            if self.on_highlight_changed:
                self.on_highlight_changed(highlight)
            
            return True
            
        except Exception as e:
            logger.error(f"ハイライト範囲調整エラー: {e}")
            return False
    
    def _text_to_quads(self, page: fitz.Page, start_pos: int, end_pos: int) -> List[fitz.Quad]:
        """テキスト位置から座標を計算"""
        try:
            # テキスト位置から文字単位の座標を取得
            text_dict = page.get_text("dict")
            
            char_count = 0
            start_coords = None
            end_coords = None
            
            for block in text_dict["blocks"]:
                if "lines" not in block:
                    continue
                    
                for line in block["lines"]:
                    for span in line["spans"]:
                        span_text = span["text"]
                        
                        for i, char in enumerate(span_text):
                            if char_count == start_pos:
                                # 開始位置の座標
                                char_bbox = fitz.Rect(span["bbox"])
                                char_width = char_bbox.width / len(span_text)
                                start_x = char_bbox.x0 + i * char_width
                                start_coords = fitz.Point(start_x, char_bbox.y0)
                            
                            if char_count == end_pos - 1:
                                # 終了位置の座標
                                char_bbox = fitz.Rect(span["bbox"])
                                char_width = char_bbox.width / len(span_text)
                                end_x = char_bbox.x0 + (i + 1) * char_width
                                end_coords = fitz.Point(end_x, char_bbox.y1)
                                break
                            
                            char_count += 1
                        
                        if start_coords and end_coords:
                            break
                    
                    if start_coords and end_coords:
                        break
                
                if start_coords and end_coords:
                    break
            
            if start_coords and end_coords:
                # Quadを作成
                quad = fitz.Quad(
                    start_coords.x, start_coords.y,
                    end_coords.x, start_coords.y,
                    end_coords.x, end_coords.y,
                    start_coords.x, end_coords.y
                )
                return [quad]
            else:
                logger.error("テキスト座標の計算に失敗")
                return []
                
        except Exception as e:
            logger.error(f"座標計算エラー: {e}")
            return []
    
    def _update_highlight_annotation(self, highlight: HighlightRegion, new_quads: List[fitz.Quad], new_text: str):
        """ハイライト注釈を更新"""
        try:
            # 既存の注釈を削除
            page = self.doc[highlight.page_num]
            page.delete_annot(highlight.annot)
            
            # 新しいハイライト注釈を作成
            new_annot = page.add_highlight_annot(new_quads)
            new_annot.set_content(f"{highlight.entity_type}: {highlight.confidence:.2%}")
            new_annot.set_info(title="Presidio Detection")
            new_annot.update()
            
            # ハイライト情報を更新
            highlight.annot = new_annot
            
        except Exception as e:
            logger.error(f"注釈更新エラー: {e}")
            raise
    
    def save_changes(self, output_path: Optional[str] = None) -> str:
        """変更を保存"""
        save_path = output_path or self.pdf_path
        
        try:
            self.doc.save(save_path, incremental=False, encryption=fitz.PDF_ENCRYPT_NONE)
            logger.info(f"変更を保存: {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"保存エラー: {e}")
            raise
    
    def close(self):
        """リソースを解放"""
        if self.doc:
            self.doc.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# 使用例とテスト用のヘルパー関数
def create_interactive_editor_demo():
    """インタラクティブエディターのデモ"""
    
    def on_highlight_changed(highlight: HighlightRegion):
        print(f"ハイライト変更: {highlight.entity_type} - '{highlight.text}'")
    
    # 使用例
    # with InteractivePDFEditor("test.pdf") as editor:
    #     editor.on_highlight_changed = on_highlight_changed
    #     
    #     # ハイライトを選択
    #     point = fitz.Point(100, 200)  # クリック座標
    #     if editor.select_highlight(0, point):
    #         # 右端を3文字拡張
    #         editor.adjust_highlight_range("right", 3)
    #         
    #         # 左端を1文字縮小
    #         editor.adjust_highlight_range("shrink_left", 1)
    #         
    #         # 変更を保存
    #         editor.save_changes("modified.pdf")

if __name__ == "__main__":
    create_interactive_editor_demo()