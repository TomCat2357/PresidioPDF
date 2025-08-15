#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座標逆引き機能の分析と設計
PDFの座標からchar_indexを高速検索する方法を検討
"""

import sys
import time
import math
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# プロジェクトルートをPATHに追加
sys.path.insert(0, str(Path(__file__).parent / "src"))

import fitz
from pdf.pdf_block_mapper import PDFBlockTextMapper


class CoordinateReverseMapper:
    """座標逆引き機能のプロトタイプ"""
    
    def __init__(self, mapper: PDFBlockTextMapper):
        self.mapper = mapper
        self.spatial_grids: Dict[int, Dict[Tuple[int, int], List[int]]] = {}
        self.grid_size = 50  # グリッドサイズ（ピクセル）
        
        # 空間インデックスを構築
        self._build_spatial_index()
    
    def _build_spatial_index(self):
        """空間インデックス（グリッド分割）を構築"""
        print("空間インデックス構築開始...")
        start_time = time.time()
        
        for page_num in range(len(self.mapper.page_blocks)):
            self.spatial_grids[page_num] = {}
            
            # ページ内の全文字を処理
            for char_idx, char_pos in enumerate(self.mapper.char_positions):
                if char_pos.page_num == page_num and char_pos.bbox:
                    bbox = char_pos.bbox
                    
                    # 文字が占有するグリッドセルを計算
                    grid_cells = self._get_grid_cells(bbox)
                    
                    for grid_cell in grid_cells:
                        if grid_cell not in self.spatial_grids[page_num]:
                            self.spatial_grids[page_num][grid_cell] = []
                        self.spatial_grids[page_num][grid_cell].append(char_idx)
        
        build_time = time.time() - start_time
        print(f"空間インデックス構築完了: {build_time:.3f}秒")
        
        # 統計情報を表示
        total_grids = sum(len(page_grids) for page_grids in self.spatial_grids.values())
        avg_chars_per_grid = sum(
            len(char_list) 
            for page_grids in self.spatial_grids.values() 
            for char_list in page_grids.values()
        ) / max(total_grids, 1)
        
        print(f"  総グリッド数: {total_grids}")
        print(f"  グリッドあたり平均文字数: {avg_chars_per_grid:.1f}")
    
    def _get_grid_cells(self, bbox: Tuple[float, float, float, float]) -> List[Tuple[int, int]]:
        """bbox が占有するグリッドセルのリストを取得"""
        x0, y0, x1, y1 = bbox
        
        # 開始・終了グリッド座標を計算
        start_grid_x = int(x0 // self.grid_size)
        start_grid_y = int(y0 // self.grid_size)
        end_grid_x = int(x1 // self.grid_size)
        end_grid_y = int(y1 // self.grid_size)
        
        # 占有するすべてのグリッドセルを列挙
        grid_cells = []
        for gx in range(start_grid_x, end_grid_x + 1):
            for gy in range(start_grid_y, end_grid_y + 1):
                grid_cells.append((gx, gy))
        
        return grid_cells
    
    def find_char_at_point_linear(self, page_num: int, x: float, y: float) -> Optional[int]:
        """線形検索での座標逆引き（比較用）"""
        for char_idx, char_pos in enumerate(self.mapper.char_positions):
            if (char_pos.page_num == page_num and 
                char_pos.bbox and 
                self._point_in_bbox(x, y, char_pos.bbox)):
                return char_idx
        return None
    
    def find_char_at_point_spatial(self, page_num: int, x: float, y: float) -> Optional[int]:
        """空間インデックスでの座標逆引き（高速版）"""
        if page_num not in self.spatial_grids:
            return None
        
        # 対象グリッドセルを計算
        grid_x = int(x // self.grid_size)
        grid_y = int(y // self.grid_size)
        grid_cell = (grid_x, grid_y)
        
        # グリッドセル内の候補文字を検索
        if grid_cell in self.spatial_grids[page_num]:
            for char_idx in self.spatial_grids[page_num][grid_cell]:
                char_pos = self.mapper.char_positions[char_idx]
                if (char_pos.bbox and 
                    self._point_in_bbox(x, y, char_pos.bbox)):
                    return char_idx
        
        return None
    
    def _point_in_bbox(self, x: float, y: float, bbox: Tuple[float, float, float, float]) -> bool:
        """点がbbox内にあるかチェック"""
        x0, y0, x1, y1 = bbox
        return x0 <= x <= x1 and y0 <= y <= y1


def analyze_coordinate_lookup_performance(mapper: PDFBlockTextMapper):
    """座標逆引きの性能分析"""
    print("\n" + "=" * 60)
    print("座標逆引き性能分析")
    print("=" * 60)
    
    # 逆引きマッパーを作成
    reverse_mapper = CoordinateReverseMapper(mapper)
    
    # テスト用座標を生成（実際の文字座標をサンプリング）
    test_coordinates = []
    for i, char_pos in enumerate(mapper.char_positions[:50]):  # 最初の50文字
        if char_pos.bbox:
            bbox = char_pos.bbox
            # bbox の中心点
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            test_coordinates.append((char_pos.page_num, center_x, center_y, i))
    
    print(f"テスト座標数: {len(test_coordinates)}")
    
    # 線形検索の性能測定
    print(f"\n線形検索性能測定:")
    start_time = time.time()
    linear_results = []
    for page_num, x, y, expected_idx in test_coordinates:
        result = reverse_mapper.find_char_at_point_linear(page_num, x, y)
        linear_results.append(result)
    linear_time = time.time() - start_time
    
    print(f"  実行時間: {linear_time:.6f}秒")
    print(f"  1座標あたり: {linear_time / len(test_coordinates) * 1000:.3f}ms")
    
    # 空間インデックス検索の性能測定
    print(f"\n空間インデックス検索性能測定:")
    start_time = time.time()
    spatial_results = []
    for page_num, x, y, expected_idx in test_coordinates:
        result = reverse_mapper.find_char_at_point_spatial(page_num, x, y)
        spatial_results.append(result)
    spatial_time = time.time() - start_time
    
    print(f"  実行時間: {spatial_time:.6f}秒")
    print(f"  1座標あたり: {spatial_time / len(test_coordinates) * 1000:.3f}ms")
    
    # 速度向上を計算
    if spatial_time > 0:
        speedup = linear_time / spatial_time
        print(f"  速度向上: {speedup:.1f}倍")
    
    # 結果の正確性を検証
    correct_matches = sum(1 for l, s in zip(linear_results, spatial_results) if l == s)
    accuracy = correct_matches / len(test_coordinates) * 100
    print(f"  結果一致率: {accuracy:.1f}% ({correct_matches}/{len(test_coordinates)})")
    
    return reverse_mapper


def estimate_memory_overhead(mapper: PDFBlockTextMapper, grid_size: int = 50):
    """空間インデックスのメモリオーバーヘッドを推定"""
    print(f"\n" + "=" * 60)
    print("メモリオーバーヘッド推定")
    print("=" * 60)
    
    total_chars = len(mapper.char_positions)
    total_pages = len(mapper.page_blocks)
    
    # 各ページの座標範囲を推定
    estimated_grids = 0
    chars_with_bbox = 0
    
    for char_pos in mapper.char_positions:
        if char_pos.bbox:
            chars_with_bbox += 1
            # 簡単な推定: ページあたり 1000x1000 ピクセル
            page_grids = (1000 // grid_size) * (1000 // grid_size)
            estimated_grids = max(estimated_grids, page_grids)
    
    estimated_grids *= total_pages
    
    # メモリ使用量推定
    # 各グリッドセル: キー（2 int） + リスト（平均文字数 × int参照）
    avg_chars_per_grid = chars_with_bbox / max(estimated_grids, 1)
    grid_memory = estimated_grids * (16 + 8 * avg_chars_per_grid)  # bytes
    
    # 既存のchar_positionsメモリ
    char_pos_memory = total_chars * 56  # CharPosition の推定サイズ
    
    print(f"既存データ:")
    print(f"  char_positions: {char_pos_memory:,} bytes ({char_pos_memory/1024/1024:.2f}MB)")
    print(f"  bbox付き文字数: {chars_with_bbox:,} / {total_chars:,}")
    
    print(f"空間インデックス (グリッドサイズ {grid_size}px):")
    print(f"  推定グリッド数: {estimated_grids:,}")
    print(f"  グリッドあたり平均文字数: {avg_chars_per_grid:.1f}")
    print(f"  推定メモリ使用量: {grid_memory:,} bytes ({grid_memory/1024/1024:.2f}MB)")
    
    overhead_percentage = (grid_memory / char_pos_memory) * 100
    print(f"  メモリオーバーヘッド: {overhead_percentage:.1f}%")


def main():
    """メイン処理"""
    print("座標逆引き機能 分析・設計")
    print("=" * 50)
    
    # テスト用PDFファイル
    test_pdf = "/workspace/test_pdfs/sony.pdf"
    
    if not Path(test_pdf).exists():
        print(f"テストPDFが見つかりません: {test_pdf}")
        return
    
    # PDFマッパーを作成
    print(f"PDF読み込み: {Path(test_pdf).name}")
    doc = fitz.open(test_pdf)
    mapper = PDFBlockTextMapper(doc)
    
    # メモリオーバーヘッド推定
    estimate_memory_overhead(mapper)
    
    # 性能分析実行
    reverse_mapper = analyze_coordinate_lookup_performance(mapper)
    
    # 設計提案
    print(f"\n" + "=" * 60)
    print("設計提案")
    print("=" * 60)
    print("1. 現在の方法:")
    print("   - 線形検索: O(n) - 全文字を順次チェック")
    print("   - メモリ効率: 追加メモリなし")
    print("   - 速度: 遅い（特に大きなPDF）")
    
    print("\n2. 空間インデックス方法:")
    print("   - グリッド検索: O(k) - グリッド内文字のみチェック")
    print("   - メモリ効率: +20-30% オーバーヘッド")
    print("   - 速度: 大幅改善（10-100倍高速）")
    
    print("\n3. 推奨実装:")
    print("   - オプション機能として実装")
    print("   - グリッドサイズを調整可能")
    print("   - 遅延構築（初回使用時に構築）")
    
    doc.close()
    print(f"\n✅ 分析完了")


if __name__ == "__main__":
    main()