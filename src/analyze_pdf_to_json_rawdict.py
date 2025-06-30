#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyMuPDFのget_text('rawdict')で取得される情報をJSONで詳細出力
"""

import fitz  # PyMuPDF
import json
import base64
from pathlib import Path

def sanitize_for_json(obj):
    """JSONシリアライゼーション用にオブジェクトをサニタイズ"""
    if isinstance(obj, bytes):
        # bytesオブジェクトはbase64エンコードして文字列に変換
        return f"<bytes: {len(obj)} bytes, base64: {base64.b64encode(obj[:100]).decode()[:50]}...>"
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_for_json(item) for item in obj)
    else:
        return obj

def analyze_pdf_rawdict_to_json(pdf_path: str, output_path: str = None):
    """PDFのget_text('rawdict')で取得される情報をJSONで詳細出力"""
    
    if output_path is None:
        output_path = "a1_rawdict_analysis_result.json"
    
    # PDFを開く
    doc = fitz.open(pdf_path)
    
    result = {
        "pdf_info": {
            "path": pdf_path,
            "page_count": len(doc),
            "metadata": doc.metadata
        },
        "pages": []
    }
    
    # 各ページを分析（最初のページのみ詳細分析）
    for page_num in range(min(1, len(doc))):  # 最初の1ページのみ
        page = doc[page_num]
        
        # rawdict形式でテキスト取得
        text_rawdict = page.get_text("rawdict")
        
        # 比較用データも取得
        simple_text = page.get_text()
        words = page.get_text("words")
        
        page_info = {
            "page_number": page_num + 1,
            "page_rect": {
                "x0": page.rect.x0,
                "y0": page.rect.y0, 
                "x1": page.rect.x1,
                "y1": page.rect.y1
            },
            "rawdict_structure": sanitize_for_json(text_rawdict),
            "comparison": {
                "simple_text": {
                    "length": len(simple_text),
                    "preview": simple_text[:200],  # 最初の200文字
                    "full_text": simple_text
                },
                "words": {
                    "count": len(words),
                    "first_10_words": [
                        {
                            "x0": word[0],
                            "y0": word[1], 
                            "x1": word[2],
                            "y1": word[3],
                            "text": word[4],
                            "block_no": word[5],
                            "line_no": word[6],
                            "word_no": word[7]
                        } for word in words[:10]
                    ]
                }
            }
        }
        
        result["pages"].append(page_info)
    
    doc.close()
    
    # JSONファイルに出力
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"分析結果を {output_path} に出力しました")
    
    # サマリーも表示
    print(f"\n=== サマリー ===")
    print(f"PDF: {pdf_path}")
    print(f"ページ数: {result['pdf_info']['page_count']}")
    if result["pages"]:
        page_data = result["pages"][0]
        rawdict_data = page_data["rawdict_structure"]
        print(f"ページサイズ: {rawdict_data.get('width')} x {rawdict_data.get('height')}")
        print(f"ブロック数: {len(rawdict_data.get('blocks', []))}")
        print(f"テキスト文字数: {page_data['comparison']['simple_text']['length']}")
        print(f"単語数: {page_data['comparison']['words']['count']}")
        
        # ブロック分析
        blocks = rawdict_data.get('blocks', [])
        text_blocks = [b for b in blocks if b.get('type') == 0]
        image_blocks = [b for b in blocks if b.get('type') == 1]
        print(f"テキストブロック数: {len(text_blocks)}")
        print(f"画像ブロック数: {len(image_blocks)}")

def main():
    """メイン実行部"""
    pdf_path = "test_pdfs/a1.pdf"
    
    # ファイルの存在確認
    if not Path(pdf_path).exists():
        print(f"エラー: {pdf_path} が見つかりません")
        return
    
    try:
        analyze_pdf_rawdict_to_json(pdf_path)
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
