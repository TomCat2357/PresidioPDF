#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDFBlockTextMapperのマッピング構造調査
データ構造の詳細を表示
"""

import sys
import json
from pathlib import Path

# プロジェクトルートをPATHに追加
sys.path.insert(0, str(Path(__file__).parent / "src"))

import fitz
from pdf.pdf_block_mapper import PDFBlockTextMapper


def analyze_mapping_structure(mapper: PDFBlockTextMapper):
    """マッピング構造を詳細分析"""
    
    print("=" * 60)
    print("PDFBlockTextMapper データ構造分析")
    print("=" * 60)
    
    # 1. 基本統計
    print(f"\n1. 基本統計:")
    print(f"   総文字数: {len(mapper.char_positions):,}")
    print(f"   総ブロック数: {len(mapper.blocks):,}")
    print(f"   総ページ数: {len(mapper.page_blocks):,}")
    
    # 2. メインデータ構造の型と構造
    print(f"\n2. メインデータ構造:")
    print(f"   char_positions: {type(mapper.char_positions)} (長さ: {len(mapper.char_positions):,})")
    print(f"   blocks: {type(mapper.blocks)} (長さ: {len(mapper.blocks):,})")
    print(f"   page_blocks: {type(mapper.page_blocks)} (長さ: {len(mapper.page_blocks):,})")
    print(f"   page_block_texts: {type(mapper.page_block_texts)} (長さ: {len(mapper.page_block_texts):,})")
    
    # 3. マッピング辞書の構造
    print(f"\n3. マッピング辞書:")
    print(f"   global_offset_to_char: {type(mapper.global_offset_to_char)} (エントリ数: {len(mapper.global_offset_to_char):,})")
    print(f"   page_block_offset_mapping: {type(mapper.page_block_offset_mapping)} (ページ数: {len(mapper.page_block_offset_mapping):,})")
    print(f"   global_block_offset_mapping: {type(mapper.global_block_offset_mapping)} (ブロック数: {len(mapper.global_block_offset_mapping):,})")
    
    # 4. page_block_offset_mappingの詳細構造
    print(f"\n4. page_block_offset_mapping構造 (ページ別):")
    for page_num, page_mapping in mapper.page_block_offset_mapping.items():
        if page_num < 3:  # 最初の3ページのみ表示
            print(f"   ページ{page_num}: {len(page_mapping)}ブロック")
            for block_id, block_mapping in list(page_mapping.items())[:3]:  # 各ページの最初の3ブロック
                print(f"     ブロック{block_id}: {len(block_mapping)}文字のマッピング")
                if len(block_mapping) > 0:
                    sample_offsets = list(block_mapping.keys())[:5]
                    print(f"       サンプルオフセット: {sample_offsets}")
    
    # 5. サンプルデータの内容
    print(f"\n5. サンプルデータ内容:")
    
    # CharPositionサンプル
    if mapper.char_positions:
        char_sample = mapper.char_positions[0]
        print(f"   CharPosition[0]: {char_sample}")
    
    # BlockInfoサンプル
    if mapper.blocks:
        block_sample = mapper.blocks[0]
        print(f"   BlockInfo[0]: {block_sample}")
    
    # 6. メモリ使用量推定
    print(f"\n6. メモリ使用量推定:")
    
    # CharPositionオブジェクトのメモリ推定 (NamedTupleの各フィールド)
    char_pos_size = 8 * 7  # 7フィールド × 8バイト (64bit参照)
    total_char_pos_memory = len(mapper.char_positions) * char_pos_size
    print(f"   char_positions: 約{total_char_pos_memory:,}バイト ({total_char_pos_memory/1024/1024:.2f}MB)")
    
    # 辞書のメモリ推定
    global_offset_memory = len(mapper.global_offset_to_char) * (8 + 8)  # key + value
    print(f"   global_offset_to_char: 約{global_offset_memory:,}バイト ({global_offset_memory/1024/1024:.2f}MB)")
    
    # page_block_offset_mappingのメモリ推定
    page_block_memory = 0
    for page_mapping in mapper.page_block_offset_mapping.values():
        for block_mapping in page_mapping.values():
            page_block_memory += len(block_mapping) * (8 + 8)  # key + value
    print(f"   page_block_offset_mapping: 約{page_block_memory:,}バイト ({page_block_memory/1024/1024:.2f}MB)")
    
    total_memory = total_char_pos_memory + global_offset_memory + page_block_memory
    print(f"   合計推定メモリ: 約{total_memory:,}バイト ({total_memory/1024/1024:.2f}MB)")
    
    # 7. データ構造効率性分析
    print(f"\n7. データ構造効率性:")
    
    # グローバルオフセット辞書の密度
    if mapper.global_offset_to_char:
        max_offset = max(mapper.global_offset_to_char.keys())
        min_offset = min(mapper.global_offset_to_char.keys())
        density = len(mapper.global_offset_to_char) / (max_offset - min_offset + 1) * 100
        print(f"   グローバルオフセット辞書密度: {density:.1f}% ({len(mapper.global_offset_to_char):,}/{max_offset-min_offset+1:,})")
    
    # ページあたりの平均ブロック数
    if mapper.page_blocks:
        avg_blocks_per_page = sum(len(page) for page in mapper.page_blocks) / len(mapper.page_blocks)
        print(f"   ページあたり平均ブロック数: {avg_blocks_per_page:.1f}")
    
    # ブロックあたりの平均文字数
    if mapper.blocks:
        avg_chars_per_block = sum(block.char_count for block in mapper.blocks) / len(mapper.blocks)
        print(f"   ブロックあたり平均文字数: {avg_chars_per_block:.1f}")


def inspect_nested_dict_structure(mapping_dict, name, max_depth=3, current_depth=0):
    """ネストした辞書構造を詳細表示"""
    if current_depth >= max_depth:
        return
    
    indent = "  " * current_depth
    print(f"{indent}{name}: {type(mapping_dict)} (キー数: {len(mapping_dict)})")
    
    # 最初のいくつかのキーを表示
    sample_keys = list(mapping_dict.keys())[:3]
    for key in sample_keys:
        value = mapping_dict[key]
        if isinstance(value, dict):
            print(f"{indent}  キー[{key}]:")
            inspect_nested_dict_structure(value, f"値", max_depth, current_depth + 2)
        else:
            print(f"{indent}  キー[{key}]: {type(value)} = {str(value)[:50]}...")


def main():
    """メイン処理"""
    # テスト用PDFファイル (小さいファイルで構造を確認)
    test_pdf = "/workspace/test_pdfs/a1.pdf"
    
    if not Path(test_pdf).exists():
        print(f"テストPDFが見つかりません: {test_pdf}")
        return
    
    print(f"マッピング構造調査: {Path(test_pdf).name}")
    
    # PDFを開いてマッパーを作成
    doc = fitz.open(test_pdf)
    mapper = PDFBlockTextMapper(doc)
    
    # 構造分析実行
    analyze_mapping_structure(mapper)
    
    # ネストした辞書構造の詳細表示
    print(f"\n" + "=" * 60)
    print("ネストした辞書構造詳細")
    print("=" * 60)
    
    inspect_nested_dict_structure(mapper.page_block_offset_mapping, "page_block_offset_mapping")
    
    doc.close()
    
    print(f"\n✅ 構造調査完了")


if __name__ == "__main__":
    main()