#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyMuPDFのget_text('rawdict')で取得される情報をJSONで詳細出力（rawdict版）
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

def analyze_characters(rawdict_data):
    """rawdictからキャラクター情報を詳細分析"""
    analysis = {
        "total_characters": 0,
        "character_samples": [],
        "blocks_with_chars": 0,
        "spans_with_chars": 0,
        "unique_fonts": set(),
        "character_distribution": {}
    }
    
    for block in rawdict_data.get('blocks', []):
        if 'lines' not in block:
            continue
            
        block_has_chars = False
        for line in block['lines']:
            for span in line.get('spans', []):
                chars = span.get('chars', [])
                if chars:
                    analysis["spans_with_chars"] += 1
                    block_has_chars = True
                    
                    # フォント情報を収集
                    font = span.get('font', 'Unknown')
                    analysis["unique_fonts"].add(font)
                    
                    for char in chars:
                        analysis["total_characters"] += 1
                        char_text = char.get('c', '')
                        
                        # 文字の分布を記録
                        if char_text in analysis["character_distribution"]:
                            analysis["character_distribution"][char_text] += 1
                        else:
                            analysis["character_distribution"][char_text] = 1
                        
                        # サンプル文字を収集（最初の20文字）
                        if len(analysis["character_samples"]) < 20:
                            analysis["character_samples"].append({
                                "char": char_text,
                                "bbox": char.get('bbox', []),
                                "font": font,
                                "size": span.get('size', 0),
                                "flags": span.get('flags', 0)
                            })
        
        if block_has_chars:
            analysis["blocks_with_chars"] += 1
    
    # セットをリストに変換（JSON化のため）
    analysis["unique_fonts"] = list(analysis["unique_fonts"])
    
    # 文字分布の上位10位を抽出
    sorted_chars = sorted(analysis["character_distribution"].items(), 
                         key=lambda x: x[1], reverse=True)
    analysis["top_10_characters"] = sorted_chars[:10]
    
    return analysis

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
        dict_text = page.get_text("dict")
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
                "dict_structure": sanitize_for_json(dict_text),
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
                },
                "character_analysis": analyze_characters(text_rawdict)
            }
        }
        
        result["pages"].append(page_info)
    
    doc.close()
    
    # JSONファイルに出力
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"分析結果を {output_path} に出力しました")
    
    # サマリーも表示
    print(f"\n=== rawdict分析サマリー ===")
    print(f"PDF: {pdf_path}")
    print(f"ページ数: {result['pdf_info']['page_count']}")
    if result["pages"]:
        page_data = result["pages"][0]
        rawdict_data = page_data["rawdict_structure"]
        char_analysis = page_data["comparison"]["character_analysis"]
        
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
        
        # 文字レベル分析
        print(f"\n=== 文字レベル分析 ===")
        print(f"総文字数: {char_analysis['total_characters']}")
        print(f"文字を含むブロック数: {char_analysis['blocks_with_chars']}")
        print(f"文字を含むスパン数: {char_analysis['spans_with_chars']}")
        print(f"ユニークフォント数: {len(char_analysis['unique_fonts'])}")
        print(f"使用フォント: {', '.join(char_analysis['unique_fonts'])}")
        
        if char_analysis['top_10_characters']:
            print(f"頻出文字Top5:")
            for char, count in char_analysis['top_10_characters'][:5]:
                char_display = repr(char) if char in [' ', '\n', '\t'] else char
                print(f"  {char_display}: {count}回")

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
