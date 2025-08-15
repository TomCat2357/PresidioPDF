#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ブロック単位PDF文字座標マッピングシステム
Fitzを使用してブロックごとのプレーンテキストと座標のマッピングを管理
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, NamedTuple
import fitz

logger = logging.getLogger(__name__)


class BlockInfo(NamedTuple):
    """ブロック情報を格納する構造体"""
    page_block_id: int  # ページ内でのブロックID (0から開始)
    global_block_id: int  # 全体でのブロックID
    page_num: int
    text: str
    bbox: Tuple[float, float, float, float]
    char_count: int


class CharPosition(NamedTuple):
    """文字位置情報を格納する構造体"""
    page_block_id: int  # ページ内でのブロックID
    global_block_id: int  # 全体でのブロックID
    block_offset: int  # ブロック内でのオフセット
    global_offset: int  # 全体でのオフセット
    page_num: int
    bbox: Optional[Tuple[float, float, float, float]]
    character: str


class PDFBlockTextMapper:
    """
    ブロック単位でのPDFテキストと座標のマッピングクラス
    
    Features:
    - ブロックごとのプレーンテキスト分割
    - ブロック内オフセット管理
    - プレーンテキスト位置からPDF座標への高速マッピング
    - Webアプリケーションでの間接的座標管理をサポート
    """

    def __init__(self, pdf_document: fitz.Document, enable_cache: bool = True):
        """
        初期化
        
        Args:
            pdf_document: PyMuPDFドキュメント
            enable_cache: キャッシュ有効化フラグ
        """
        self.pdf_document = pdf_document
        self.enable_cache = enable_cache
        
        # ページ別ブロックデータ
        self.page_blocks: List[List[BlockInfo]] = []  # page_num → [BlockInfo]
        self.page_block_texts: List[List[str]] = []  # page_num → [block_text]
        
        # 全体データ（後方互換性のため）
        self.blocks: List[BlockInfo] = []
        self.block_texts: List[str] = []
        
        # 文字位置データ
        self.char_positions: List[CharPosition] = []
        
        # 高速検索用マッピング
        self.global_offset_to_char: Dict[int, int] = {}  # グローバルオフセット → char_positions index
        self.page_block_offset_mapping: Dict[int, Dict[int, Dict[int, int]]] = {}  # page_num → page_block_id → {block_offset: char_positions index}
        self.global_block_offset_mapping: Dict[int, Dict[int, int]] = {}  # global_block_id → {block_offset: char_positions index}
        
        # キャッシュ
        self._coordinate_cache: Optional[Dict[str, List[Dict]]] = {} if enable_cache else None
        
        # 統計
        self.stats = {
            "total_blocks": 0,
            "total_chars": 0,
            "total_pages": 0,
            "processing_time": 0.0
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
            self.blocks.clear()
            self.block_texts.clear()
            self.char_positions.clear()
            
            global_block_counter = 0
            global_char_index = 0
            
            for page_num in range(len(self.pdf_document)):
                page = self.pdf_document[page_num]
                page_blocks_data = self._extract_page_blocks(page, page_num, global_block_counter, global_char_index)
                
                # ページ別データ構築
                page_block_infos = []
                page_block_text_list = []
                
                for block_info, block_chars in page_blocks_data:
                    # ページ別リストに追加
                    page_block_infos.append(block_info)
                    page_block_text_list.append(block_info.text)
                    
                    # 全体リストに追加（後方互換性）
                    self.blocks.append(block_info)
                    self.block_texts.append(block_info.text)
                    self.char_positions.extend(block_chars)
                    
                    global_block_counter += 1
                    global_char_index += len(block_chars)
                
                self.page_blocks.append(page_block_infos)
                self.page_block_texts.append(page_block_text_list)
            
            # マッピング構築
            self._build_mappings()
            
            # 統計更新
            self.stats.update({
                "total_blocks": len(self.blocks),
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
        start_global_block_id: int, 
        start_global_char_index: int
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
            global_block_id = start_global_block_id
            global_char_index = start_global_char_index
            
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
                                global_block_id=global_block_id,
                                block_offset=block_offset,
                                global_offset=global_char_index,
                                page_num=page_num,
                                bbox=tuple(bbox) if bbox else None,
                                character=char
                            )
                            
                            block_text_chars.append(char)
                            block_char_positions.append(char_pos)
                            
                            block_offset += 1
                            global_char_index += 1
                
                if block_text_chars:
                    # ブロック情報を作成
                    block_info = BlockInfo(
                        page_block_id=page_block_id,
                        global_block_id=global_block_id,
                        page_num=page_num,
                        text="".join(block_text_chars),
                        bbox=tuple(block_bbox),
                        char_count=len(block_text_chars)
                    )
                    
                    page_blocks.append((block_info, block_char_positions))
                    page_block_id += 1
                    global_block_id += 1
            
            return page_blocks
            
        except Exception as e:
            logger.error(f"ページ{page_num}ブロック抽出エラー: {e}")
            return []

    def _build_mappings(self):
        """高速検索用マッピングを構築"""
        try:
            self.global_offset_to_char.clear()
            self.page_block_offset_mapping.clear()
            self.global_block_offset_mapping.clear()
            
            for i, char_pos in enumerate(self.char_positions):
                # グローバルオフセットマッピング
                self.global_offset_to_char[char_pos.global_offset] = i
                
                # ページ・ブロック内オフセットマッピング
                page_num = char_pos.page_num
                page_block_id = char_pos.page_block_id
                
                if page_num not in self.page_block_offset_mapping:
                    self.page_block_offset_mapping[page_num] = {}
                
                if page_block_id not in self.page_block_offset_mapping[page_num]:
                    self.page_block_offset_mapping[page_num][page_block_id] = {}
                
                self.page_block_offset_mapping[page_num][page_block_id][char_pos.block_offset] = i
                
                # グローバルブロック内オフセットマッピング（後方互換性）
                global_block_id = char_pos.global_block_id
                if global_block_id not in self.global_block_offset_mapping:
                    self.global_block_offset_mapping[global_block_id] = {}
                
                self.global_block_offset_mapping[global_block_id][char_pos.block_offset] = i
            
            logger.debug(f"マッピング構築完了: {len(self.char_positions)}文字位置")
            
        except Exception as e:
            logger.error(f"マッピング構築エラー: {e}")

    def get_block_texts(self) -> List[str]:
        """
        ブロックごとのプレーンテキストリストを取得（後方互換性）
        
        Returns:
            List[str]: ブロックごとのプレーンテキスト
        """
        return self.block_texts.copy()
    
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

    def get_block_info(self, global_block_id: int) -> Optional[BlockInfo]:
        """
        指定グローバルブロックの情報を取得（後方互換性）
        
        Args:
            global_block_id: グローバルブロックID
            
        Returns:
            Optional[BlockInfo]: ブロック情報（存在しない場合はNone）
        """
        for block in self.blocks:
            if block.global_block_id == global_block_id:
                return block
        return None
    
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
    
    def map_block_offset_to_coordinates(
        self, 
        global_block_id: int, 
        start_offset: int, 
        end_offset: int
    ) -> List[Dict[str, Any]]:
        """
        グローバルブロック内オフセットからPDF座標を取得（後方互換性）
        
        Args:
            global_block_id: グローバルブロックID
            start_offset: 開始オフセット（ブロック内）
            end_offset: 終了オフセット（ブロック内）
            
        Returns:
            List[Dict]: 座標情報リスト
        """
        try:
            # キャッシュチェック
            cache_key = f"global_block_{global_block_id}_{start_offset}_{end_offset}"
            if self._coordinate_cache and cache_key in self._coordinate_cache:
                return self._coordinate_cache[cache_key]
            
            # 範囲検証
            if global_block_id not in self.global_block_offset_mapping:
                logger.warning(f"存在しないグローバルブロックID: {global_block_id}")
                return []
            
            block_mapping = self.global_block_offset_mapping[global_block_id]
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
                logger.warning(f"座標取得失敗: グローバルブロック{global_block_id}, オフセット{start_offset}-{end_offset}")
                return []
            
            # ページごとにグループ化して矩形作成
            page_groups: Dict[int, List] = {}
            for coord in char_coords:
                page = coord["page"]
                if page not in page_groups:
                    page_groups[page] = []
                page_groups[page].append(coord["bbox"])
            
            # 各ページの境界矩形を計算
            result_rects = []
            for page, bboxes in page_groups.items():
                if bboxes:
                    x0 = min(bbox[0] for bbox in bboxes)
                    y0 = min(bbox[1] for bbox in bboxes)
                    x1 = max(bbox[2] for bbox in bboxes)
                    y1 = max(bbox[3] for bbox in bboxes)
                    
                    text_chars = [coord["char"] for coord in char_coords if coord["page"] == page]
                    text = "".join(text_chars)
                    
                    result_rects.append({
                        "page_num": page,
                        "rect": fitz.Rect(x0, y0, x1, y1),
                        "text": text
                    })
            
            # キャッシュに保存
            if self._coordinate_cache:
                self._coordinate_cache[cache_key] = result_rects
            
            logger.debug(
                f"グローバルブロック座標マッピング成功: ブロック{global_block_id}, "
                f"オフセット{start_offset}-{end_offset} -> {len(result_rects)}矩形"
            )
            
            return result_rects
            
        except Exception as e:
            logger.error(
                f"グローバルブロックオフセット座標マッピングエラー: "
                f"ブロック{global_block_id}, オフセット{start_offset}-{end_offset}, エラー: {e}"
            )
            return []

    def map_global_offset_to_coordinates(
        self, 
        start_offset: int, 
        end_offset: int
    ) -> List[Dict[str, Any]]:
        """
        グローバルオフセットからPDF座標を取得
        
        Args:
            start_offset: 開始オフセット（全体）
            end_offset: 終了オフセット（全体）
            
        Returns:
            List[Dict]: 座標情報リスト
        """
        try:
            # キャッシュチェック
            cache_key = f"global_{start_offset}_{end_offset}"
            if self._coordinate_cache and cache_key in self._coordinate_cache:
                return self._coordinate_cache[cache_key]
            
            # 範囲検証
            if start_offset >= end_offset or start_offset < 0 or end_offset > len(self.char_positions):
                logger.warning(f"無効なグローバルオフセット範囲: {start_offset}-{end_offset}")
                return []
            
            # 対象文字位置を収集
            char_coords = []
            for offset in range(start_offset, end_offset):
                if offset in self.global_offset_to_char:
                    char_idx = self.global_offset_to_char[offset]
                    char_pos = self.char_positions[char_idx]
                    
                    if char_pos.bbox:
                        char_coords.append({
                            "bbox": char_pos.bbox,
                            "page": char_pos.page_num,
                            "global_block": char_pos.global_block_id,
                            "char": char_pos.character
                        })
            
            if not char_coords:
                logger.warning(f"グローバル座標取得失敗: オフセット{start_offset}-{end_offset}")
                return []
            
            # ブロックとページでグループ化
            groups: Dict[Tuple[int, int], List] = {}
            for coord in char_coords:
                key = (coord["page"], coord["global_block"])
                if key not in groups:
                    groups[key] = []
                groups[key].append(coord)
            
            # 各グループの矩形を計算
            result_rects = []
            for (page, global_block), coords in groups.items():
                bboxes = [coord["bbox"] for coord in coords]
                
                if bboxes:
                    x0 = min(bbox[0] for bbox in bboxes)
                    y0 = min(bbox[1] for bbox in bboxes)
                    x1 = max(bbox[2] for bbox in bboxes)
                    y1 = max(bbox[3] for bbox in bboxes)
                    
                    text = "".join(coord["char"] for coord in coords)
                    
                    result_rects.append({
                        "page_num": page,
                        "global_block_id": global_block,
                        "rect": fitz.Rect(x0, y0, x1, y1),
                        "text": text
                    })
            
            # キャッシュに保存
            if self._coordinate_cache:
                self._coordinate_cache[cache_key] = result_rects
            
            logger.debug(
                f"グローバル座標マッピング成功: オフセット{start_offset}-{end_offset} "
                f"-> {len(result_rects)}矩形"
            )
            
            return result_rects
            
        except Exception as e:
            logger.error(
                f"グローバルオフセット座標マッピングエラー: "
                f"オフセット{start_offset}-{end_offset}, エラー: {e}"
            )
            return []

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
    
    def find_text_in_blocks(self, search_text: str) -> List[Dict[str, Any]]:
        """
        全ブロックでテキストを検索（後方互換性）
        
        Args:
            search_text: 検索テキスト
            
        Returns:
            List[Dict]: 検索結果リスト
        """
        results = []
        
        try:
            for page_num in range(len(self.page_block_texts)):
                page_results = self.find_text_in_page_blocks(page_num, search_text)
                results.extend(page_results)
            
            logger.debug(f"全ブロックテキスト検索完了: '{search_text}' -> {len(results)}件")
            return results
            
        except Exception as e:
            logger.error(f"全ブロックテキスト検索エラー: '{search_text}', エラー: {e}")
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
                "global_block_id": block.global_block_id,
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
    
    def get_block_summary(self) -> List[Dict[str, Any]]:
        """
        全ブロックの要約情報を取得（後方互換性）
        
        Returns:
            List[Dict]: ブロック要約リスト
        """
        summary = []
        
        for block in self.blocks:
            summary.append({
                "page_block_id": block.page_block_id,
                "global_block_id": block.global_block_id,
                "page_num": block.page_num,
                "char_count": block.char_count,
                "text_preview": block.text[:100] + "..." if len(block.text) > 100 else block.text,
                "bbox": block.bbox
            })
        
        return summary

    def clear_cache(self):
        """キャッシュをクリア"""
        if self._coordinate_cache:
            self._coordinate_cache.clear()
            logger.debug("座標キャッシュをクリアしました")

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        cache_size = len(self._coordinate_cache) if self._coordinate_cache else 0
        
        return {
            **self.stats,
            "cache_entries": cache_size,
            "blocks_info": [
                {
                    "page_block_id": block.page_block_id,
                    "global_block_id": block.global_block_id,
                    "page_num": block.page_num,
                    "char_count": block.char_count
                }
                for block in self.blocks[:10]  # 最初の10ブロックのみ表示
            ]
        }