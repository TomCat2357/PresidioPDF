#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡易版：改行を跨ぐ文字の正確な座標解析
PDFTextLocatorの内部データを直接活用
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict

# プロジェクトモジュールをインポート
sys.path.append('src')
from presidio_web_core import PresidioPDFWebApp
from pdf_locator import PDFTextLocator

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_tanaka_characters():
    """田中太郎と田中太朗の正確な文字座標を解析"""
    test_pdf_path = "./test_japanese_linebreaks.pdf"
    
    if not os.path.exists(test_pdf_path):
        logger.error(f"テストファイルが見つかりません: {test_pdf_path}")
        return
    
    try:
        print("="*80)
        print("田中太郎/田中太朗の正確な文字座標解析")
        print("="*80)
        
        # PresidioPDFWebAppを初期化
        session_id = "simple_analysis"
        web_app = PresidioPDFWebApp(session_id, use_gpu=False)
        
        # PDFファイルを読み込み
        result = web_app.load_pdf_file(test_pdf_path)
        if not result['success']:
            raise Exception(f"PDF読み込みエラー: {result['message']}")
        
        # 個人情報検出を実行
        detection_result = web_app.run_detection()
        if not detection_result['success']:
            raise Exception(f"検出エラー: {detection_result['message']}")
        
        entities = detection_result['results']
        
        # 田中関連エンティティを抽出
        tanaka_entities = [e for e in entities if '田中' in e['text']]
        print(f"田中関連エンティティ: {len(tanaka_entities)}件")
        
        # PDFTextLocatorのデータを直接取得
        import fitz
        pdf_document = fitz.open(test_pdf_path)
        locator = PDFTextLocator(pdf_document)
        
        print(f"\nPDFTextLocator情報:")
        print(f"- 通常テキスト長: {len(locator.full_text)}")
        print(f"- 改行なしテキスト長: {len(locator.full_text_no_newlines)}")
        print(f"- char_data要素数: {len(locator.char_data)}")
        
        # 改行なしテキストを表示
        print(f"\n改行なしテキスト（最初の100文字）:")
        print(f"'{locator.full_text_no_newlines[:100]}'")
        
        # 田中関連エンティティの詳細解析
        for i, entity in enumerate(tanaka_entities, 1):
            print(f"\n【田中関連PII #{i}: {entity['text']}】")
            print(f"オフセット: {entity['start']}-{entity['end']}")
            
            # 改行なしテキストからPII文字列を抽出
            start, end = entity['start'], entity['end']
            if end <= len(locator.full_text_no_newlines):
                extracted = locator.full_text_no_newlines[start:end]
                print(f"抽出されたテキスト: '{extracted}'")
                print(f"期待テキスト: '{entity['text']}'")
                print(f"一致: {'✅' if extracted == entity['text'] else '❌'}")
            
            # PDFTextLocatorの座標矩形を取得
            coord_rects = locator.locate_pii_by_offset_no_newlines(start, end)
            print(f"取得された矩形数: {len(coord_rects)}")
            
            for j, rect in enumerate(coord_rects):
                print(f"  矩形{j+1}: ({rect.x0:.2f}, {rect.y0:.2f}) - ({rect.x1:.2f}, {rect.y1:.2f})")
            
            # line_rectsの詳細
            line_rects = entity.get('line_rects', [])
            print(f"line_rects数: {len(line_rects)}")
            for j, line_rect in enumerate(line_rects):
                rect_info = line_rect['rect']
                print(f"  line_rect{j+1}: ({rect_info['x0']:.2f}, {rect_info['y0']:.2f}) - ({rect_info['x1']:.2f}, {rect_info['y1']:.2f})")
        
        # char_dataから田中関連文字を手動検索
        print(f"\n【char_dataから田中関連文字を検索】")
        tanaka_chars_in_char_data = []
        for i, char_info in enumerate(locator.char_data):
            char = char_info.get('char', '')
            if char in ['田', '中', '太', '郎', '朗']:
                tanaka_chars_in_char_data.append({
                    'index': i,
                    'char': char,
                    'bbox': char_info.get('bbox'),
                    'page': char_info.get('page', 0),
                    'line': char_info.get('line', 0),
                    'block': char_info.get('block', 0)
                })
        
        print(f"char_dataで見つかった田中関連文字: {len(tanaka_chars_in_char_data)}個")
        for char_info in tanaka_chars_in_char_data:
            bbox = char_info['bbox']
            if bbox:
                print(f"  [{char_info['index']:3d}] '{char_info['char']}' -> ({bbox[0]:.2f}, {bbox[1]:.2f}) - ({bbox[2]:.2f}, {bbox[3]:.2f}) [行:{char_info['line']} ブロック:{char_info['block']}]")
            else:
                print(f"  [{char_info['index']:3d}] '{char_info['char']}' -> 座標なし")
        
        # 改行なしテキストと char_data のマッピング状況を確認
        print(f"\n【テキスト同期確認】")
        print("改行なしテキストの最初の20文字:")
        for i in range(min(20, len(locator.full_text_no_newlines))):
            char = locator.full_text_no_newlines[i]
            print(f"  [{i:2d}] '{char}'")
        
        print("\nchar_dataの最初の30文字:")
        for i in range(min(30, len(locator.char_data))):
            char_info = locator.char_data[i]
            char = char_info.get('char', '')
            print(f"  [{i:2d}] '{char}' {'(改行)' if char == chr(10) else ''}")
        
        pdf_document.close()
        
    except Exception as e:
        logger.error(f"解析エラー: {e}")
        raise

if __name__ == "__main__":
    analyze_tanaka_characters()