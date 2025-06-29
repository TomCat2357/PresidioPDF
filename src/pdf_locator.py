#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF内のテキストと座標のマッピング
"""

import logging
import fitz  # PyMuPDF
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

class PDFTextLocator:
    """
    PDF文書の文字レベル情報と、PII検出用のプレーンテキストを同期させ、
    テキストオフセットから直接、精密な座標を算出するクラス。
    """
    def __init__(self, pdf_doc: fitz.Document):
        """
        コンストラクタ。fitz.Documentオブジェクトを受け取り、
        PII検出用の「フルテキスト」と、文字ごとの「キャラクターデータリスト」を準備する。

        Args:
            pdf_doc (fitz.Document): 対象のPDFドキュメントオブジェクト。
        """
        self.doc = pdf_doc
        self.full_text, self.char_data = self._prepare_synced_data()
        self.full_text_no_newlines = self.full_text.replace('\n', '').replace('\r', '')
        self._create_offset_mapping()

    def _prepare_synced_data(self) -> Tuple[str, List[Dict]]:
        """
        `page.get_text("rawdict")`を使い、PDFの全文字情報を抽出。
        PII検出用テキストと文字情報リストを完全に同期させた状態で生成する。
        """
        char_data = []
        text_parts = []
        
        for page in self.doc:
            page_dict = page.get_text("rawdict")
            page_num = page.number
            
            for block_num, block in enumerate(page_dict.get('blocks', [])):
                if 'lines' not in block:
                    continue
                
                for line_num, line in enumerate(block['lines']):
                    spans = line.get('spans', [])
                    
                    for span_idx, span in enumerate(spans):
                        chars = span.get('chars', [])
                        
                        for char in chars:
                            char_text = char.get('c', '')
                            text_parts.append(char_text)
                            
                            char_data.append({
                                'char': char_text,
                                'rect': fitz.Rect(char['bbox']),
                                'page_num': page_num,
                                'line_num': line_num,
                                'block_num': block_num
                            })
                        
                        if span_idx < len(spans) - 1:
                            next_span = spans[span_idx + 1]
                            current_span_end = span['bbox'][2]
                            next_span_start = next_span['bbox'][0]
                    
                            if next_span_start - current_span_end > 1.0:
                                text_parts.append(' ')
                                space_rect = fitz.Rect(
                                    current_span_end, span['bbox'][1],
                                    next_span_start, span['bbox'][3]
                                )
                                char_data.append({
                                    'char': ' ',
                                    'rect': space_rect,
                                    'page_num': page_num,
                                    'line_num': line_num,
                                    'block_num': block_num
                                })
                    
                    if line_num < len(block['lines']) - 1:
                        text_parts.append('\n')
                        if line.get('spans'):
                            last_span = line['spans'][-1]
                            newline_rect = fitz.Rect(
                                last_span['bbox'][2], last_span['bbox'][1],
                                last_span['bbox'][2] + 5, last_span['bbox'][3]
                            )
                            char_data.append({
                                'char': '\n',
                                'rect': newline_rect,
                                'page_num': page_num,
                                'line_num': line_num,
                                'block_num': block_num
                            })
                
                if block_num < len(page_dict['blocks']) - 1:
                    text_parts.append('\n')
                    if block.get('lines') and block['lines'][-1].get('spans'):
                        last_line = block['lines'][-1]
                        last_span = last_line['spans'][-1]
                        newline_rect = fitz.Rect(
                            last_span['bbox'][0], last_span['bbox'][3],
                            last_span['bbox'][2], last_span['bbox'][3] + 5
                        )
                        char_data.append({
                            'char': '\n',
                            'rect': newline_rect,
                            'page_num': page_num,
                            'line_num': len(block['lines']),
                            'block_num': block_num
                        })
            
            if page_num < len(self.doc) - 1:
                text_parts.append('\n')
                page_rect = page.rect
                newline_rect = fitz.Rect(
                    page_rect.x0, page_rect.y1 - 5,
                    page_rect.x0 + 5, page_rect.y1
                )
                char_data.append({
                    'char': '\n',
                    'rect': newline_rect,
                    'page_num': page_num,
                    'line_num': 0,
                    'block_num': 0
                })
        
        full_text = "".join(text_parts)
        return full_text, char_data

    def locate_pii_by_offset(self, start: int, end: int) -> List[fitz.Rect]:
        """
        フルテキストにおける文字の開始・終了オフセットを受け取り、
        対応するキャラクターデータの矩形を結合して、最終的な座標リストを返す。
        """
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
            lines[key].append(char_info['rect'])
        
        final_rects = []
        for line_rects in lines.values():
            if line_rects:
                combined_rect = line_rects[0]
                for rect in line_rects[1:]:
                    combined_rect = combined_rect + rect
                final_rects.append(combined_rect)
        
        return final_rects

    def _create_offset_mapping(self):
        """
        改行なしテキストのオフセットを元テキストのオフセットにマップするテーブルを作成
        """
        self.no_newlines_to_original = {}
        no_newlines_pos = 0
        
        for original_pos, char in enumerate(self.full_text):
            if char not in ['\n', '\r']:
                self.no_newlines_to_original[no_newlines_pos] = original_pos
                no_newlines_pos += 1

    def locate_pii_by_offset_no_newlines(self, start: int, end: int) -> List[fitz.Rect]:
        """
        改行なしテキストでのオフセットを受け取り、元テキストのオフセットに変換してから座標を取得
        """
        # 改行なしテキストのオフセットを元テキストのオフセットに変換
        original_start = self.no_newlines_to_original.get(start, start)
        original_end = self.no_newlines_to_original.get(end - 1, end - 1) + 1
        
        return self.locate_pii_by_offset(original_start, original_end)