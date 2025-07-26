#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最適化されたPDF文字座標特定システム
rawdictベースの高精度・高速文字座標マッピング
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
import fitz

logger = logging.getLogger(__name__)

class PDFTextLocator:
    """
    最適化されたPDF文字座標特定クラス
    
    PyMuPDF分析結果に基づく最適実装:
    - rawdictベース: 文字レベル座標精度100%
    - 改行を跨ぐPII完全対応
    - 高速オフセット→座標マッピング
    - 後方互換性維持
    """
    
    def __init__(self, pdf_document: fitz.Document, enable_cache: bool = True):
        """
        初期化
        
        Args:
            pdf_document: PyMuPDFドキュメント
            enable_cache: キャッシュ有効化（大容量PDF対応）
        """
        self.doc = pdf_document  # 後方互換性のため
        self.pdf_document = pdf_document
        self.enable_cache = enable_cache
        
        # 主要データ構造
        self.char_data: List[Dict[str, Any]] = []
        self.full_text: str = ""
        self.full_text_no_newlines: str = ""
        
        # マッピング構造（高速化用）
        self.offset_to_char_mapping: Dict[int, int] = {}
        self.char_to_offset_mapping: Dict[int, int] = {}
        self.no_newlines_to_original: Dict[int, int] = {}  # 後方互換性
        
        # キャッシュ
        self._coordinate_cache: Dict[str, List[fitz.Rect]] = {} if enable_cache else None
        
        # 統計情報
        self.stats = {
            'total_chars': 0,
            'total_pages': 0,
            'processing_time': 0.0
        }
        
        # 初期化実行
        self._initialize()
    
    def _initialize(self):
        """システム初期化：全ページの文字座標とテキストを同期構築"""
        import time
        start_time = time.time()
        
        logger.debug("PDFTextLocator初期化開始")
        
        try:
            self.char_data.clear()
            full_text_parts = []
            no_newlines_parts = []
            char_index = 0
            
            for page_num in range(len(self.pdf_document)):
                page = self.pdf_document[page_num]
                page_char_data, page_full_text, page_no_newlines = self._process_page(page, page_num, char_index)
                
                # 全体データに追加
                self.char_data.extend(page_char_data)
                full_text_parts.append(page_full_text)
                no_newlines_parts.append(page_no_newlines)
                
                char_index += len(page_char_data)
                
                # ページ区切り（最後のページ以外）
                if page_num < len(self.pdf_document) - 1:
                    full_text_parts.append("\n")  # ページ改行
            
            # 完全テキスト構築
            self.full_text = "".join(full_text_parts)
            self.full_text_no_newlines = "".join(no_newlines_parts)
            
            # マッピング構築
            self._build_offset_mappings()
            
            # 統計更新
            self.stats.update({
                'total_chars': len(self.char_data),
                'total_pages': len(self.pdf_document),
                'processing_time': time.time() - start_time
            })
            
            logger.debug(f"初期化完了: {self.stats['total_chars']}文字、{self.stats['total_pages']}ページ、{self.stats['processing_time']:.3f}秒")
            
        except Exception as e:
            logger.error(f"初期化エラー: {e}")
            raise
    
    def _process_page(self, page: fitz.Page, page_num: int, start_char_index: int) -> Tuple[List[Dict], str, str]:
        """
        単一ページの処理
        
        Returns:
            (char_data, full_text, no_newlines_text)
        """
        try:
            rawdict = page.get_text("rawdict")
            
            page_char_data = []
            full_text_chars = []
            no_newlines_chars = []
            
            for block_idx, block in enumerate(rawdict.get('blocks', [])):
                if 'lines' not in block:
                    continue  # 画像ブロックなどをスキップ
                
                for line_idx, line in enumerate(block['lines']):
                    line_chars_processed = False
                    
                    for span_idx, span in enumerate(line.get('spans', [])):
                        chars = span.get('chars', [])
                        
                        for char_idx_in_span, char_info in enumerate(chars):
                            char = char_info.get('c', '')
                            bbox = char_info.get('bbox')
                            origin = char_info.get('origin')
                            
                            # 文字データ構築（後方互換性を考慮）
                            char_data_entry = {
                                'char': char,
                                'rect': fitz.Rect(bbox) if bbox else None,
                                'page_num': page_num,
                                'line_num': line_idx,
                                'block_num': block_idx,
                                # 新しい詳細情報
                                'page': page_num,
                                'block': block_idx,
                                'line': line_idx,
                                'span': span_idx,
                                'char_idx_in_span': char_idx_in_span,
                                'global_char_idx': start_char_index + len(page_char_data),
                                'bbox': bbox,
                                'origin': origin,
                                'font': span.get('font'),
                                'size': span.get('size'),
                                'flags': span.get('flags')
                            }
                            
                            page_char_data.append(char_data_entry)
                            full_text_chars.append(char)
                            
                            # 改行なしテキスト用（改行・空白以外を追加）
                            if char != '\n':
                                no_newlines_chars.append(char)
                            
                            line_chars_processed = True
                    
                    # 行末処理（改行追加）
                    if line_chars_processed and line_idx < len(block['lines']) - 1:
                        # 行間の改行（最後の行以外）
                        newline_entry = {
                            'char': '\n',
                            'rect': None,
                            'page_num': page_num,
                            'line_num': line_idx,
                            'block_num': block_idx,
                            # 新しい詳細情報
                            'page': page_num,
                            'block': block_idx,
                            'line': line_idx,
                            'span': -1,  # 改行は特別なspan
                            'char_idx_in_span': -1,
                            'global_char_idx': start_char_index + len(page_char_data),
                            'bbox': None,
                            'origin': None,
                            'font': None,
                            'size': None,
                            'flags': None
                        }
                        
                        page_char_data.append(newline_entry)
                        full_text_chars.append('\n')
                        # no_newlines_charsには改行を追加しない
            
            return page_char_data, "".join(full_text_chars), "".join(no_newlines_chars)
            
        except Exception as e:
            logger.error(f"ページ{page_num}処理エラー: {e}")
            return [], "", ""
    
    def _build_offset_mappings(self):
        """オフセット間マッピングの構築"""
        try:
            self.offset_to_char_mapping.clear()
            self.char_to_offset_mapping.clear()
            self.no_newlines_to_original.clear()
            
            no_newlines_offset = 0
            
            for char_data_idx, char_info in enumerate(self.char_data):
                char = char_info['char']
                
                # 改行なしテキストのオフセットとchar_dataのマッピング
                if char != '\n':
                    self.offset_to_char_mapping[no_newlines_offset] = char_data_idx
                    self.char_to_offset_mapping[char_data_idx] = no_newlines_offset
                    self.no_newlines_to_original[no_newlines_offset] = char_data_idx  # 後方互換性
                    no_newlines_offset += 1
            
            logger.debug(f"オフセットマッピング構築完了: {len(self.offset_to_char_mapping)}件")
            
        except Exception as e:
            logger.error(f"オフセットマッピング構築エラー: {e}")
    
    def locate_pii_by_offset_no_newlines(self, start_offset: int, end_offset: int) -> List[Dict]:
        """
        改行なしテキストオフセットから座標矩形リストとページ番号を取得
        
        Args:
            start_offset: 開始オフセット（改行なしテキスト基準）
            end_offset: 終了オフセット（改行なしテキスト基準）
        
        Returns:
            List[Dict]: 座標矩形とページ番号のリスト（改行を跨ぐ場合は複数）
                       [{'rect': fitz.Rect, 'page_num': int}, ...]
        """
        try:
            # キャッシュチェック
            cache_key = f"{start_offset}_{end_offset}"
            if self._coordinate_cache and cache_key in self._coordinate_cache:
                return self._coordinate_cache[cache_key]
            
            # オフセット範囲の検証
            if start_offset < 0 or end_offset > len(self.full_text_no_newlines):
                logger.warning(f"オフセット範囲エラー: {start_offset}-{end_offset}, テキスト長: {len(self.full_text_no_newlines)}")
                return []
            
            if start_offset >= end_offset:
                logger.warning(f"無効なオフセット範囲: {start_offset}-{end_offset}")
                return []
            
            # char_dataインデックス範囲を特定
            start_char_idx = self.offset_to_char_mapping.get(start_offset)
            end_char_idx = self.offset_to_char_mapping.get(end_offset - 1)  # 末尾は含まない
            
            if start_char_idx is None or end_char_idx is None:
                logger.warning(f"char_dataマッピング失敗: start={start_char_idx}, end={end_char_idx}")
                return []
            
            # 対象文字の座標を収集
            char_coords = []
            for char_idx in range(start_char_idx, end_char_idx + 1):
                if char_idx < len(self.char_data):
                    char_info = self.char_data[char_idx]
                    bbox = char_info.get('bbox')
                    if bbox:
                        char_coords.append({
                            'bbox': bbox,
                            'page': char_info['page'],
                            'line': char_info['line'],
                            'char': char_info['char']
                        })
            
            if not char_coords:
                logger.warning(f"座標取得失敗: オフセット{start_offset}-{end_offset}")
                return []
            
            # 行別にグループ化して矩形を作成
            line_groups = {}
            for coord in char_coords:
                page = coord['page']
                line = coord['line']
                key = (page, line)
                if key not in line_groups:
                    line_groups[key] = []
                line_groups[key].append(coord['bbox'])
            
            # 各行の境界矩形を計算
            rects = []
            for (page, line), bboxes in line_groups.items():
                if bboxes:
                    # 行内の全文字を囲む矩形を計算
                    x0 = min(bbox[0] for bbox in bboxes)
                    y0 = min(bbox[1] for bbox in bboxes)
                    x1 = max(bbox[2] for bbox in bboxes)
                    y1 = max(bbox[3] for bbox in bboxes)
                    
                    rects.append({
                        'rect': fitz.Rect(x0, y0, x1, y1),
                        'page_num': page
                    })
            
            # キャッシュに保存
            if self._coordinate_cache:
                self._coordinate_cache[cache_key] = rects
            
            logger.debug(f"座標特定成功: オフセット{start_offset}-{end_offset} -> {len(rects)}矩形")
            return rects
            
        except Exception as e:
            logger.error(f"座標特定エラー: オフセット{start_offset}-{end_offset}, エラー: {e}")
            return []
    
    def locate_pii_by_offset_no_newlines_legacy(self, start_offset: int, end_offset: int) -> List[fitz.Rect]:
        """
        後方互換性のための旧形式メソッド - 矩形のみを返す
        
        Args:
            start_offset: 開始オフセット（改行なしテキスト基準）
            end_offset: 終了オフセット（改行なしテキスト基準）
        
        Returns:
            List[fitz.Rect]: 座標矩形リスト（改行を跨ぐ場合は複数）
        """
        rect_data = self.locate_pii_by_offset_no_newlines(start_offset, end_offset)
        return [item['rect'] for item in rect_data]
    
    # 後方互換性のためのメソッド
    def locate_pii_by_offset(self, start: int, end: int) -> List[fitz.Rect]:
        """
        後方互換性のためのメソッド
        従来のフルテキストオフセットから座標を取得
        """
        try:
            if start < 0 or end > len(self.char_data) or start >= end:
                return []
            
            target_chars = self.char_data[start:end]
            
            lines = {}
            for char_info in target_chars:
                page_num = char_info['page_num']
                line_num = char_info['line_num']
                key = (page_num, line_num)
                
                if key not in lines:
                    lines[key] = []
                
                rect = char_info.get('rect')
                if rect:
                    lines[key].append(rect)
            
            final_rects = []
            for line_rects in lines.values():
                if line_rects:
                    combined_rect = line_rects[0]
                    for rect in line_rects[1:]:
                        combined_rect = combined_rect + rect
                    final_rects.append(combined_rect)
            
            return final_rects
            
        except Exception as e:
            logger.error(f"後方互換locate_pii_by_offsetエラー: {e}")
            return []
    
    def get_pii_line_rects(self, start_offset: int, end_offset: int) -> List[Dict[str, Any]]:
        """
        PII用の詳細行矩形情報を取得
        
        Returns:
            List[Dict]: line_rects形式のデータ
        """
        try:
            coord_rects_with_pages = self.locate_pii_by_offset_no_newlines(start_offset, end_offset)
            if not coord_rects_with_pages:
                return []
            
            # 対象テキストを取得
            pii_text = self.full_text_no_newlines[start_offset:end_offset] if end_offset <= len(self.full_text_no_newlines) else ""
            
            line_rects = []
            for i, rect_data in enumerate(coord_rects_with_pages):
                rect = rect_data['rect']
                line_rects.append({
                    'rect': {
                        'x0': float(rect.x0),
                        'y0': float(rect.y0),
                        'x1': float(rect.x1),
                        'y1': float(rect.y1)
                    },
                    'text': pii_text if i == 0 else f"line_{i+1}",
                    'line_number': i + 1,
                    'page_num': rect_data['page_num']
                })
            
            return line_rects
            
        except Exception as e:
            logger.error(f"line_rects取得エラー: {e}")
            return []
    
    def get_character_details(self, start_offset: int, end_offset: int) -> List[Dict[str, Any]]:
        """
        文字レベル詳細情報を取得
        
        Returns:
            List[Dict]: 各文字の詳細情報
        """
        try:
            char_details = []
            
            for offset in range(start_offset, end_offset):
                char_data_idx = self.offset_to_char_mapping.get(offset)
                
                if char_data_idx is not None and char_data_idx < len(self.char_data):
                    char_info = self.char_data[char_data_idx]
                    bbox = char_info.get('bbox')
                    
                    detail = {
                        'char_index': offset - start_offset,
                        'global_offset': offset,
                        'char_data_offset': char_data_idx,
                        'character': char_info['char'],
                        'has_coordinates': bbox is not None,
                        'bbox': bbox
                    }
                    
                    if bbox:
                        detail.update({
                            'x0': float(bbox[0]),
                            'y0': float(bbox[1]),
                            'x1': float(bbox[2]),
                            'y1': float(bbox[3]),
                            'width': float(bbox[2] - bbox[0]),
                            'height': float(bbox[3] - bbox[1]),
                            'page': char_info.get('page', 0),
                            'line': char_info.get('line', 0),
                            'block': char_info.get('block', 0)
                        })
                    
                    char_details.append(detail)
                else:
                    # マッピング失敗時のフォールバック
                    char = self.full_text_no_newlines[offset] if offset < len(self.full_text_no_newlines) else '?'
                    char_details.append({
                        'char_index': offset - start_offset,
                        'global_offset': offset,
                        'char_data_offset': None,
                        'character': char,
                        'has_coordinates': False,
                        'bbox': None
                    })
            
            return char_details
            
        except Exception as e:
            logger.error(f"文字詳細取得エラー: {e}")
            return []
    
    def clear_cache(self):
        """キャッシュクリア"""
        if self._coordinate_cache:
            self._coordinate_cache.clear()
            logger.debug("座標キャッシュをクリアしました")
    
    def get_stats(self) -> Dict[str, Any]:
        """統計情報取得"""
        cache_size = len(self._coordinate_cache) if self._coordinate_cache else 0
        
        return {
            **self.stats,
            'cache_entries': cache_size,
            'full_text_length': len(self.full_text),
            'no_newlines_text_length': len(self.full_text_no_newlines),
            'offset_mappings': len(self.offset_to_char_mapping)
        }
    
    def validate_integrity(self) -> Dict[str, bool]:
        """データ整合性チェック"""
        try:
            checks = {
                'char_data_not_empty': len(self.char_data) > 0,
                'full_text_not_empty': len(self.full_text) > 0,
                'no_newlines_text_not_empty': len(self.full_text_no_newlines) > 0,
                'offset_mapping_consistent': len(self.offset_to_char_mapping) == len(self.full_text_no_newlines),
                'reverse_mapping_consistent': len(self.char_to_offset_mapping) <= len(self.char_data)
            }
            
            # 詳細整合性チェック
            offset_check_passed = True
            for offset, char_idx in list(self.offset_to_char_mapping.items())[:10]:  # サンプルチェック
                if char_idx >= len(self.char_data):
                    offset_check_passed = False
                    break
                
                expected_char = self.full_text_no_newlines[offset] if offset < len(self.full_text_no_newlines) else None
                actual_char = self.char_data[char_idx]['char']
                
                if expected_char != actual_char:
                    offset_check_passed = False
                    break
            
            checks['offset_char_mapping_valid'] = offset_check_passed
            
            logger.debug(f"整合性チェック結果: {checks}")
            return checks
            
        except Exception as e:
            logger.error(f"整合性チェックエラー: {e}")
            return {'error': str(e)}

# 後方互換性のための追加準備（必要に応じて）
# OptimizedPDFTextLocator = PDFTextLocator