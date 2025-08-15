#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ページベース PDF文字座標マッピングシステム（リファクタリング版）
グローバル構造を完全削除し、双方向座標変換機能を追加
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, NamedTuple
import fitz

logger = logging.getLogger(__name__)


class BlockInfo(NamedTuple):
    """ブロック情報を格納する構造体"""
    page_block_id: int  # ページ内でのブロックID (0から開始)
    page_num: int
    text: str
    bbox: Tuple[float, float, float, float]
    char_count: int


class CharPosition(NamedTuple):
    """文字位置情報を格納する構造体"""
    page_block_id: int  # ページ内でのブロックID
    block_offset: int  # ブロック内でのオフセット
    page_num: int
    bbox: Optional[Tuple[float, float, float, float]]
    character: str


class PDFBlockTextMapper:
    """
    ページベースPDFテキストと座標の双方向マッピングクラス
    
    Features:
    - ページ・ブロック単位での完全管理
    - オフセット→座標変換
    - 座標→オフセット逆引き（空間インデックス）
    - グローバル構造完全削除
    """

    def __init__(self, pdf_document: fitz.Document, enable_cache: bool = True, enable_spatial_index: bool = True):
        """
        初期化
        
        Args:
            pdf_document: PyMuPDFドキュメント
            enable_cache: キャッシュ有効化フラグ
            enable_spatial_index: 空間インデックス有効化フラグ
        """
        self.pdf_document = pdf_document
        self.enable_cache = enable_cache
        self.enable_spatial_index = enable_spatial_index
        
        # ページベースデータ構造
        self.page_blocks: List[List[BlockInfo]] = []  # page_num → [BlockInfo]
        self.page_block_texts: List[List[str]] = []  # page_num → [block_text]
        self.char_positions: List[CharPosition] = []  # 全文字位置（インデックス用のみ）
        
        # 高速検索用マッピング
        self.page_block_offset_mapping: Dict[int, Dict[int, Dict[int, int]]] = {}  # page_num → page_block_id → {block_offset: char_positions index}
        
        # 空間インデックス（座標逆引き用）
        self.spatial_grids: Dict[int, Dict[Tuple[int, int], List[int]]] = {}  # page_num → {(grid_x, grid_y): [char_indices]}
        self.grid_size = 50  # グリッドサイズ（ピクセル）
        
        # キャッシュ
        self._coordinate_cache: Optional[Dict[str, List[Dict]]] = {} if enable_cache else None
        
        # 統計
        self.stats = {
            "total_blocks": 0,
            "total_chars": 0,
            "total_pages": 0,
            "processing_time": 0.0,
            "spatial_index_enabled": enable_spatial_index
        }
        
        # 初期化実行
        self._initialize()

    def _initialize(self):
        """システム初期化: 全ページのブロック分析とマッピング構築"""
        import time
        start_time = time.time()
        
        logger.debug("PDFBlockTextMapper初期化開始")
        
        try:
            self.page_blocks.clear()
            self.page_block_texts.clear()
            self.char_positions.clear()
            
            char_index = 0
            
            for page_num in range(len(self.pdf_document)):
                page = self.pdf_document[page_num]
                page_blocks_data = self._extract_page_blocks(page, page_num, char_index)
                
                # ページ別データ構築
                page_block_infos = []
                page_block_text_list = []
                
                for block_info, block_chars in page_blocks_data:
                    page_block_infos.append(block_info)
                    page_block_text_list.append(block_info.text)
                    self.char_positions.extend(block_chars)
                    char_index += len(block_chars)
                
                self.page_blocks.append(page_block_infos)
                self.page_block_texts.append(page_block_text_list)
            
            # マッピング構築
            self._build_mappings()
            
            # 空間インデックス構築
            if self.enable_spatial_index:
                self._build_spatial_index()
            
            # 統計更新
            total_blocks = sum(len(page_blocks) for page_blocks in self.page_blocks)
            self.stats.update({
                "total_blocks": total_blocks,
                "total_chars": len(self.char_positions),
                "total_pages": len(self.pdf_document),
                "processing_time": time.time() - start_time
            })
            
            logger.debug(
                f"初期化完了: {self.stats['total_blocks']}ブロック、"
                f"{self.stats['total_chars']}文字、{self.stats['processing_time']:.3f}秒"
            )
            
        except Exception as e:
            logger.error(f"初期化エラー: {e}")
            raise

    def _extract_page_blocks(
        self, 
        page: fitz.Page, 
        page_num: int, 
        start_char_index: int
    ) -> List[Tuple[BlockInfo, List[CharPosition]]]:
        """
        単一ページからブロック情報を抽出
        
        Returns:
            List[Tuple[BlockInfo, List[CharPosition]]]: (ブロック情報, 文字位置リスト) のペア
        """
        page_blocks = []
        
        try:
            rawdict = page.get_text("rawdict")
            page_block_id = 0  # ページ内ブロックID（0から開始）
            char_index = start_char_index
            
            for block_data in rawdict.get("blocks", []):
                if "lines" not in block_data:
                    continue  # 画像ブロックなどをスキップ
                
                # ブロック境界矩形を計算
                block_bbox = block_data.get("bbox")
                if not block_bbox:
                    continue
                
                # ブロック内のテキストと文字位置を抽出
                block_text_chars = []
                block_char_positions = []
                block_offset = 0
                
                for line in block_data["lines"]:
                    for span in line.get("spans", []):
                        chars = span.get("chars", [])
                        
                        for char_info in chars:
                            char = char_info.get("c", "")
                            bbox = char_info.get("bbox")
                            
                            # 文字位置情報を作成
                            char_pos = CharPosition(
                                page_block_id=page_block_id,
                                block_offset=block_offset,
                                page_num=page_num,
                                bbox=tuple(bbox) if bbox else None,
                                character=char
                            )
                            
                            block_text_chars.append(char)
                            block_char_positions.append(char_pos)
                            
                            block_offset += 1
                            char_index += 1
                
                if block_text_chars:
                    # ブロック情報を作成
                    block_info = BlockInfo(
                        page_block_id=page_block_id,
                        page_num=page_num,
                        text="".join(block_text_chars),
                        bbox=tuple(block_bbox),
                        char_count=len(block_text_chars)
                    )
                    
                    page_blocks.append((block_info, block_char_positions))
                    page_block_id += 1
            
            return page_blocks
            
        except Exception as e:
            logger.error(f"ページ{page_num}ブロック抽出エラー: {e}")
            return []

    def _build_mappings(self):
        """高速検索用マッピングを構築"""
        try:
            self.page_block_offset_mapping.clear()
            
            for i, char_pos in enumerate(self.char_positions):
                page_num = char_pos.page_num
                page_block_id = char_pos.page_block_id
                
                if page_num not in self.page_block_offset_mapping:
                    self.page_block_offset_mapping[page_num] = {}
                
                if page_block_id not in self.page_block_offset_mapping[page_num]:
                    self.page_block_offset_mapping[page_num][page_block_id] = {}
                
                self.page_block_offset_mapping[page_num][page_block_id][char_pos.block_offset] = i
            
            logger.debug(f"マッピング構築完了: {len(self.char_positions)}文字位置")
            
        except Exception as e:
            logger.error(f"マッピング構築エラー: {e}")

    def _build_spatial_index(self):
        """空間インデックス（グリッド分割）を構築"""
        try:
            logger.debug("空間インデックス構築開始")
            start_time = __import__('time').time()
            
            self.spatial_grids.clear()
            
            for page_num in range(len(self.page_blocks)):
                self.spatial_grids[page_num] = {}
                
                # ページ内の全文字を処理
                for char_idx, char_pos in enumerate(self.char_positions):
                    if char_pos.page_num == page_num and char_pos.bbox:
                        bbox = char_pos.bbox
                        
                        # 文字が占有するグリッドセルを計算
                        grid_cells = self._get_grid_cells(bbox)
                        
                        for grid_cell in grid_cells:
                            if grid_cell not in self.spatial_grids[page_num]:
                                self.spatial_grids[page_num][grid_cell] = []
                            self.spatial_grids[page_num][grid_cell].append(char_idx)
            
            build_time = __import__('time').time() - start_time
            logger.debug(f"空間インデックス構築完了: {build_time:.3f}秒")
            
        except Exception as e:
            logger.error(f"空間インデックス構築エラー: {e}")

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

    def get_page_block_texts(self, page_num: int) -> List[str]:
        """
        指定ページのブロックテキストリストを取得
        
        Args:
            page_num: ページ番号
            
        Returns:
            List[str]: ページ内のブロックテキストリスト
        """
        if 0 <= page_num < len(self.page_block_texts):
            return self.page_block_texts[page_num].copy()
        return []
    
    def get_all_page_block_texts(self) -> List[List[str]]:
        """
        全ページのブロックテキストリストを取得
        
        Returns:
            List[List[str]]: page_num → [block_text]
        """
        return [page_texts.copy() for page_texts in self.page_block_texts]

    def get_page_block_info(self, page_num: int, page_block_id: int) -> Optional[BlockInfo]:
        """
        指定ページの指定ブロック情報を取得
        
        Args:
            page_num: ページ番号
            page_block_id: ページ内ブロックID
            
        Returns:
            Optional[BlockInfo]: ブロック情報（存在しない場合はNone）
        """
        if 0 <= page_num < len(self.page_blocks):
            page_block_list = self.page_blocks[page_num]
            if 0 <= page_block_id < len(page_block_list):
                return page_block_list[page_block_id]
        return None

    def map_page_block_offset_to_coordinates(
        self, 
        page_num: int,
        page_block_id: int, 
        start_offset: int, 
        end_offset: int
    ) -> List[Dict[str, Any]]:
        """
        ページ内ブロックのオフセットからPDF座標を取得
        
        Args:
            page_num: ページ番号
            page_block_id: ページ内ブロックID
            start_offset: 開始オフセット（ブロック内）
            end_offset: 終了オフセット（ブロック内）
            
        Returns:
            List[Dict]: 座標情報リスト
                [{'page_num': int, 'rect': fitz.Rect, 'text': str, 'page_block_id': int}, ...]
        """
        try:
            # キャッシュチェック
            cache_key = f"page_{page_num}_block_{page_block_id}_{start_offset}_{end_offset}"
            if self._coordinate_cache and cache_key in self._coordinate_cache:
                return self._coordinate_cache[cache_key]
            
            # 範囲検証
            if page_num not in self.page_block_offset_mapping:
                logger.warning(f"存在しないページ: {page_num}")
                return []
            
            if page_block_id not in self.page_block_offset_mapping[page_num]:
                logger.warning(f"存在しないページ内ブロックID: ページ{page_num}, ブロック{page_block_id}")
                return []
            
            block_mapping = self.page_block_offset_mapping[page_num][page_block_id]
            if start_offset >= end_offset or start_offset < 0:
                logger.warning(f"無効なオフセット範囲: {start_offset}-{end_offset}")
                return []
            
            # 対象文字位置を収集
            char_coords = []
            for offset in range(start_offset, end_offset):
                if offset in block_mapping:
                    char_idx = block_mapping[offset]
                    char_pos = self.char_positions[char_idx]
                    
                    if char_pos.bbox:
                        char_coords.append({
                            "bbox": char_pos.bbox,
                            "page": char_pos.page_num,
                            "char": char_pos.character
                        })
            
            if not char_coords:
                logger.warning(f"座標取得失敗: ページ{page_num}, ブロック{page_block_id}, オフセット{start_offset}-{end_offset}")
                return []
            
            # 全文字を囲む矩形を計算
            bboxes = [coord["bbox"] for coord in char_coords]
            x0 = min(bbox[0] for bbox in bboxes)
            y0 = min(bbox[1] for bbox in bboxes)
            x1 = max(bbox[2] for bbox in bboxes)
            y1 = max(bbox[3] for bbox in bboxes)
            
            # テキストを取得
            text = "".join(coord["char"] for coord in char_coords)
            
            result_rects = [{
                "page_num": page_num,
                "page_block_id": page_block_id,
                "rect": fitz.Rect(x0, y0, x1, y1),
                "text": text
            }]
            
            # キャッシュに保存
            if self._coordinate_cache:
                self._coordinate_cache[cache_key] = result_rects
            
            logger.debug(
                f"ページブロック座標マッピング成功: ページ{page_num}, ブロック{page_block_id}, "
                f"オフセット{start_offset}-{end_offset} -> {len(result_rects)}矩形"
            )
            
            return result_rects
            
        except Exception as e:
            logger.error(
                f"ページブロックオフセット座標マッピングエラー: "
                f"ページ{page_num}, ブロック{page_block_id}, オフセット{start_offset}-{end_offset}, エラー: {e}"
            )
            return []

    def find_offset_at_coordinates(self, page_num: int, x: float, y: float) -> Optional[Dict[str, Any]]:
        """
        指定座標のページ・ブロック・オフセット情報を取得（座標→オフセット逆引き）
        
        Args:
            page_num: ページ番号
            x: X座標
            y: Y座標
            
        Returns:
            Optional[Dict]: 座標にある文字の詳細情報
                {'page_num': int, 'page_block_id': int, 'block_offset': int, 'character': str, 'char_index': int}
        """
        if not self.enable_spatial_index:
            # 空間インデックスが無効な場合は線形検索
            return self._find_offset_linear(page_num, x, y)
        
        return self._find_offset_spatial(page_num, x, y)

    def _find_offset_spatial(self, page_num: int, x: float, y: float) -> Optional[Dict[str, Any]]:
        """空間インデックスでの座標逆引き"""
        try:
            if page_num not in self.spatial_grids:
                return None
            
            # 対象グリッドセルを計算
            grid_x = int(x // self.grid_size)
            grid_y = int(y // self.grid_size)
            grid_cell = (grid_x, grid_y)
            
            # グリッドセル内の候補文字を検索
            if grid_cell in self.spatial_grids[page_num]:
                for char_idx in self.spatial_grids[page_num][grid_cell]:
                    char_pos = self.char_positions[char_idx]
                    if (char_pos.bbox and 
                        self._point_in_bbox(x, y, char_pos.bbox)):
                        return {
                            "page_num": char_pos.page_num,
                            "page_block_id": char_pos.page_block_id,
                            "block_offset": char_pos.block_offset,
                            "character": char_pos.character,
                            "char_index": char_idx
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"空間インデックス座標逆引きエラー: ページ{page_num}, 座標({x}, {y}), エラー: {e}")
            return None

    def _find_offset_linear(self, page_num: int, x: float, y: float) -> Optional[Dict[str, Any]]:
        """線形検索での座標逆引き"""
        try:
            for char_idx, char_pos in enumerate(self.char_positions):
                if (char_pos.page_num == page_num and 
                    char_pos.bbox and 
                    self._point_in_bbox(x, y, char_pos.bbox)):
                    return {
                        "page_num": char_pos.page_num,
                        "page_block_id": char_pos.page_block_id,
                        "block_offset": char_pos.block_offset,
                        "character": char_pos.character,
                        "char_index": char_idx
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"線形座標逆引きエラー: ページ{page_num}, 座標({x}, {y}), エラー: {e}")
            return None

    def _point_in_bbox(self, x: float, y: float, bbox: Tuple[float, float, float, float]) -> bool:
        """点がbbox内にあるかチェック"""
        x0, y0, x1, y1 = bbox
        return x0 <= x <= x1 and y0 <= y <= y1

    def find_text_in_page_blocks(self, page_num: int, search_text: str) -> List[Dict[str, Any]]:
        """
        指定ページのブロック内でテキストを検索し、位置情報を取得
        
        Args:
            page_num: ページ番号
            search_text: 検索テキスト
            
        Returns:
            List[Dict]: 検索結果リスト
                [{'page_num': int, 'page_block_id': int, 'start_offset': int, 'end_offset': int, 
                  'coordinates': List[Dict], 'text': str}, ...]
        """
        results = []
        
        try:
            if page_num < 0 or page_num >= len(self.page_block_texts):
                logger.warning(f"無効なページ番号: {page_num}")
                return []
            
            page_block_list = self.page_block_texts[page_num]
            
            for page_block_id, block_text in enumerate(page_block_list):
                start_pos = 0
                while True:
                    pos = block_text.find(search_text, start_pos)
                    if pos == -1:
                        break
                    
                    end_pos = pos + len(search_text)
                    coordinates = self.map_page_block_offset_to_coordinates(
                        page_num, page_block_id, pos, end_pos
                    )
                    
                    results.append({
                        "page_num": page_num,
                        "page_block_id": page_block_id,
                        "start_offset": pos,
                        "end_offset": end_pos,
                        "coordinates": coordinates,
                        "text": search_text
                    })
                    
                    start_pos = pos + 1
            
            logger.debug(f"ページテキスト検索完了: ページ{page_num}, '{search_text}' -> {len(results)}件")
            return results
            
        except Exception as e:
            logger.error(f"ページテキスト検索エラー: ページ{page_num}, '{search_text}', エラー: {e}")
            return []

    def get_page_block_summary(self, page_num: int) -> List[Dict[str, Any]]:
        """
        指定ページのブロック要約情報を取得
        
        Args:
            page_num: ページ番号
            
        Returns:
            List[Dict]: ページ内ブロック要約リスト
        """
        if page_num < 0 or page_num >= len(self.page_blocks):
            return []
        
        summary = []
        page_block_list = self.page_blocks[page_num]
        
        for block in page_block_list:
            summary.append({
                "page_num": block.page_num,
                "page_block_id": block.page_block_id,
                "char_count": block.char_count,
                "text_preview": block.text[:100] + "..." if len(block.text) > 100 else block.text,
                "bbox": block.bbox
            })
        
        return summary
    
    def get_all_page_block_summary(self) -> List[List[Dict[str, Any]]]:
        """
        全ページのブロック要約情報を取得
        
        Returns:
            List[List[Dict]]: page_num → [block_summary]
        """
        return [self.get_page_block_summary(page_num) for page_num in range(len(self.page_blocks))]

    def clear_cache(self):
        """キャッシュをクリア"""
        if self._coordinate_cache:
            self._coordinate_cache.clear()
            logger.debug("座標キャッシュをクリアしました")

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        cache_size = len(self._coordinate_cache) if self._coordinate_cache else 0
        
        # 空間インデックス統計
        spatial_stats = {}
        if self.enable_spatial_index:
            total_grids = sum(len(page_grids) for page_grids in self.spatial_grids.values())
            total_grid_entries = sum(
                len(char_list) 
                for page_grids in self.spatial_grids.values() 
                for char_list in page_grids.values()
            )
            spatial_stats = {
                "spatial_grids": total_grids,
                "spatial_grid_entries": total_grid_entries,
                "avg_chars_per_grid": total_grid_entries / max(total_grids, 1)
            }
        
        return {
            **self.stats,
            "cache_entries": cache_size,
            **spatial_stats,
            "page_structure": [
                {
                    "page_num": page_num,
                    "block_count": len(self.page_blocks[page_num]),
                    "char_count": sum(block.char_count for block in self.page_blocks[page_num])
                }
                for page_num in range(min(5, len(self.page_blocks)))  # 最初の5ページのみ表示
            ]
        }