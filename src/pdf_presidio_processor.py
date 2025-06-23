#%%!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyMuPDFのget_text('dict')で取得される情報をJSONで詳細出力（修正・機能追加版）
"""

import fitz  # PyMuPDF
import json
import base64
from pathlib import Path
import traceback

def sanitize_for_json(obj):
    """JSONシリアライゼーション用にオブジェクトをサニタイズ"""
    if isinstance(obj, bytes):
        # bytesオブジェクトはbase64エンコードして文字列に変換
        # 全てをエンコードすると長くなりすぎるため、先頭部分のみのプレビューとする
        return f"<bytes: {len(obj)} bytes, base64_preview: {base64.b64encode(obj[:100]).decode()[:50]}...>"
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_for_json(item) for item in obj)
    else:
        return obj

def analyze_pdf_to_dict(pdf_path: str) -> dict:
    """
    PDFを分析し、結果をPythonの辞書オブジェクトとして返す（中核ロジック）
    """
    doc = fitz.open(pdf_path)
    
    result = {
        "pdf_info": {
            "path": pdf_path,
            "page_count": len(doc),
            "metadata": sanitize_for_json(doc.metadata) # メタデータもサニタイズ
        },
        "pages": []
    }
    
    try:
        # 各ページを分析（ここでは最初の1ページのみに限定）
        for page_num in range(min(1, len(doc))):
            page = doc[page_num]
            
            # dict形式でテキスト取得
            text_dict = page.get_text("dict")
            
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
                "dict_structure": sanitize_for_json(text_dict),
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
    finally:
        doc.close()
        
    return result

def analyze_pdf_to_json_string(pdf_path: str) -> str:
    """
    【新設】PDFの分析結果をJSON文字列として返す
    
    Args:
        pdf_path (str): 分析対象のPDFファイルパス

    Returns:
        str: 分析結果のJSON文字列
    """
    analysis_dict = analyze_pdf_to_dict(pdf_path)
    return json.dumps(analysis_dict, ensure_ascii=False, indent=2)

def analyze_pdf_dict_to_json_file(pdf_path: str, output_path: str = None):
    """
    【旧関数・修正版】PDFの分析結果をJSONファイルに出力する
    """
    if output_path is None:
        # 出力パスが指定されない場合、元のファイル名に基づいて生成
        p = Path(pdf_path)
        output_path = p.with_name(f"{p.stem}_analysis_result.json")
    
    # 中核となる分析関数を呼び出す
    result = analyze_pdf_to_dict(pdf_path)
    
    # JSONファイルに出力
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"分析結果を {output_path} に出力しました")
    
    # サマリーも表示
    print(f"\n=== サマリー ({pdf_path}) ===")
    print(f"ページ数: {result['pdf_info']['page_count']}")
    if result["pages"]:
        page_data = result["pages"][0]
        dict_data = page_data["dict_structure"]
        print(f"ページサイズ: {dict_data.get('width')} x {dict_data.get('height')}")
        print(f"ブロック数: {len(dict_data.get('blocks', []))}")
        print(f"テキスト文字数: {page_data['comparison']['simple_text']['length']}")
        print(f"単語数: {page_data['comparison']['words']['count']}")
        
        blocks = dict_data.get('blocks', [])
        text_blocks = [b for b in blocks if b.get('type') == 0]
        image_blocks = [b for b in blocks if b.get('type') == 1]
        print(f"テキストブロック数: {len(text_blocks)}")
        print(f"画像ブロック数: {len(image_blocks)}")

def main():
    """メイン実行部"""
    pdf_path = "./test_pdfs/a1.pdf"
    
    if not Path(pdf_path).exists():
        print(f"エラー: テスト用PDF '{pdf_path}' が見つかりません。")
        print("スクリプトと同じ階層に 'test_pdfs' フォルダを作成し、その中に 'a1.pdf' を配置してください。")
        return
    
    try:
        # --- 従来のファイル出力機能の実行 ---
        print("--- 1. 分析結果をファイルに出力 ---")
        analyze_pdf_dict_to_json_file(pdf_path)
        
        print("\n" + "="*50 + "\n")

        # --- 新設したJSON文字列を返す関数の実行 ---
        print("--- 2. 分析結果をJSON文字列として取得 ---")
        json_output = analyze_pdf_to_json_string(pdf_path)
        
        print(f"'{pdf_path}' の分析結果をJSON文字列として取得しました。")
        print("以下に最初の500文字を出力します。")
        print("-" * 20)
        print(json_output[:500] + "...")
        print("-" * 20)
        
        # 例えば、返されたJSON文字列を再度パースして利用することも可能
        data_from_string = json.loads(json_output)
        print(f"\n再パース成功。PDFのページ数: {data_from_string['pdf_info']['page_count']}")

    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        traceback.print_exc()
#%%
if __name__ == "__main__":
    main()
#%%

