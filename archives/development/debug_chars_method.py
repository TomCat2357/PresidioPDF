#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get_text('chars')メソッドの詳細デバッグ
"""

import os
import sys
import fitz

def debug_chars_method():
    """get_text('chars')メソッドのデバッグ"""
    test_pdf_path = "./test_japanese_linebreaks.pdf"
    
    if not os.path.exists(test_pdf_path):
        print(f"テストファイルが見つかりません: {test_pdf_path}")
        return
    
    try:
        pdf_document = fitz.open(test_pdf_path)
        page = pdf_document[0]
        
        print("=== get_text('chars') デバッグ ===")
        
        # 各種get_textメソッドをテスト
        methods = ['chars', 'words', 'dict', 'rawdict']
        
        for method in methods:
            try:
                print(f"\n■ get_text('{method}'):")
                result = page.get_text(method)
                
                if method == 'chars':
                    print(f"  型: {type(result)}")
                    print(f"  長さ: {len(result) if result else 0}")
                    if result:
                        print(f"  最初の5要素:")
                        for i, item in enumerate(result[:5]):
                            print(f"    [{i}] {item}")
                
                elif method == 'words':
                    print(f"  型: {type(result)}")
                    print(f"  単語数: {len(result) if result else 0}")
                    
                elif method in ['dict', 'rawdict']:
                    print(f"  型: {type(result)}")
                    if isinstance(result, dict):
                        print(f"  キー: {list(result.keys())}")
                        blocks = result.get('blocks', [])
                        print(f"  ブロック数: {len(blocks)}")
                        
                        if method == 'rawdict' and blocks:
                            # rawdictの文字レベル情報をチェック
                            char_count = 0
                            for block in blocks[:1]:  # 最初のブロックのみ
                                if 'lines' in block:
                                    for line in block['lines'][:1]:  # 最初の行のみ
                                        for span in line.get('spans', [])[:1]:  # 最初のspanのみ
                                            chars = span.get('chars', [])
                                            char_count += len(chars)
                                            print(f"    span内文字数: {len(chars)}")
                                            if chars:
                                                print(f"    最初の文字: {chars[0]}")
                            print(f"  合計文字数（サンプル）: {char_count}")
                
            except Exception as e:
                print(f"  エラー: {e}")
        
        pdf_document.close()
        
    except Exception as e:
        print(f"デバッグエラー: {e}")

if __name__ == "__main__":
    debug_chars_method()