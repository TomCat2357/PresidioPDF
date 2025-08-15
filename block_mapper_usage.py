#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDFBlockTextMapper使用例
ブロック単位でのPDFテキスト・座標マッピングの実用例
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import fitz
from pdf.pdf_block_mapper import PDFBlockTextMapper


def demo_usage():
    """PDFBlockTextMapperの基本的な使用方法のデモ"""
    
    # 1. PDFファイルを開く
    pdf_path = "/workspace/test_pdfs/sony.pdf"
    doc = fitz.open(pdf_path)
    
    # 2. ブロックマッパーを初期化
    mapper = PDFBlockTextMapper(doc)
    
    # 3. ブロックごとのプレーンテキストリストを取得
    block_texts = mapper.get_block_texts()
    print(f"総ブロック数: {len(block_texts)}")
    
    # 4. Webフロントエンドでのユーザーインタラクション例
    # ユーザーがブロック0の文字1-3を選択したとする
    selected_block_id = 0
    selected_start = 1
    selected_end = 3
    
    # 5. 選択されたテキストを確認
    if selected_block_id < len(block_texts):
        selected_text = block_texts[selected_block_id][selected_start:selected_end]
        print(f"選択テキスト: '{selected_text}'")
        
        # 6. バックエンドでPDF座標を解決
        coordinates = mapper.map_block_offset_to_coordinates(
            selected_block_id, selected_start, selected_end
        )
        
        # 7. 座標情報を出力（マスキングやハイライト処理で使用）
        for coord in coordinates:
            rect = coord["rect"]
            print(f"ページ{coord['page_num']}: 座標({rect.x0:.1f}, {rect.y0:.1f}, {rect.x1:.1f}, {rect.y1:.1f})")


if __name__ == "__main__":
    demo_usage()