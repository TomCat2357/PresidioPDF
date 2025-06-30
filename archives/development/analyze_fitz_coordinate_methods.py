#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyMuPDF (fitz) 文字座標取得メソッドの包括的調査・分析
改行を跨ぐPII対応に最適な手法を特定する
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FitzCoordinateMethodAnalyzer:
    """PyMuPDF文字座標取得メソッドの包括的分析"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pdf_document = None
        self.analysis_results = {}
        
    def analyze_all_methods(self) -> Dict[str, Any]:
        """全ての文字座標取得メソッドを分析"""
        try:
            logger.info(f"PyMuPDF文字座標メソッド分析開始: {self.pdf_path}")
            
            self.pdf_document = fitz.open(self.pdf_path)
            page = self.pdf_document[0]  # 最初のページを使用
            
            methods_to_analyze = [
                ('get_text_chars', self._analyze_get_text_chars),
                ('get_text_words', self._analyze_get_text_words),
                ('get_text_blocks', self._analyze_get_text_blocks),
                ('get_text_dict', self._analyze_get_text_dict),
                ('get_text_rawdict', self._analyze_get_text_rawdict),
                ('get_textpage_ocr', self._analyze_get_textpage_ocr),
                ('search_for', self._analyze_search_for),
                ('get_texttrace', self._analyze_get_texttrace)
            ]
            
            for method_name, analyzer_func in methods_to_analyze:
                logger.info(f"分析中: {method_name}")
                try:
                    start_time = time.time()
                    result = analyzer_func(page)
                    end_time = time.time()
                    
                    result['execution_time'] = end_time - start_time
                    result['method_name'] = method_name
                    self.analysis_results[method_name] = result
                    
                    logger.info(f"{method_name} 完了: {result['execution_time']:.3f}秒")
                    
                except Exception as e:
                    logger.error(f"{method_name} エラー: {e}")
                    self.analysis_results[method_name] = {
                        'method_name': method_name,
                        'error': str(e),
                        'execution_time': None
                    }
            
            return self.analysis_results
            
        except Exception as e:
            logger.error(f"全体分析エラー: {e}")
            raise
        finally:
            if self.pdf_document:
                self.pdf_document.close()
    
    def _analyze_get_text_chars(self, page: fitz.Page) -> Dict[str, Any]:
        """get_text("chars")メソッドの分析"""
        try:
            chars = page.get_text("chars")
            
            # 田中関連文字を検索
            tanaka_chars = []
            for i, char_info in enumerate(chars):
                char = char_info[4]  # [x0, y0, x1, y1, char, flags, font, size]
                if char in ['田', '中', '太', '郎', '朗']:
                    tanaka_chars.append({
                        'index': i,
                        'char': char,
                        'bbox': [char_info[0], char_info[1], char_info[2], char_info[3]],
                        'flags': char_info[5],
                        'font': char_info[6],
                        'size': char_info[7]
                    })
            
            return {
                'total_chars': len(chars),
                'tanaka_chars_found': len(tanaka_chars),
                'tanaka_chars': tanaka_chars,
                'sample_chars': chars[:5] if chars else [],
                'data_structure': 'List[Tuple[x0, y0, x1, y1, char, flags, font, size]]',
                'pros': ['個別文字座標が正確', 'フォント情報含む', 'シンプルな構造'],
                'cons': ['行・ブロック情報なし', '大量のデータ'],
                'precision': 'high',
                'speed': 'medium'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_get_text_words(self, page: fitz.Page) -> Dict[str, Any]:
        """get_text("words")メソッドの分析"""
        try:
            words = page.get_text("words")
            
            # 田中関連単語を検索
            tanaka_words = []
            for i, word_info in enumerate(words):
                word = word_info[4]  # [x0, y0, x1, y1, word, block_no, line_no, word_no]
                if any(char in word for char in ['田', '中', '太', '郎', '朗']):
                    tanaka_words.append({
                        'index': i,
                        'word': word,
                        'bbox': [word_info[0], word_info[1], word_info[2], word_info[3]],
                        'block_no': word_info[5],
                        'line_no': word_info[6],
                        'word_no': word_info[7]
                    })
            
            return {
                'total_words': len(words),
                'tanaka_words_found': len(tanaka_words),
                'tanaka_words': tanaka_words,
                'sample_words': words[:5] if words else [],
                'data_structure': 'List[Tuple[x0, y0, x1, y1, word, block_no, line_no, word_no]]',
                'pros': ['行・ブロック情報含む', '単語レベル構造化', '高速'],
                'cons': ['文字レベル座標なし', '単語境界に依存'],
                'precision': 'medium',
                'speed': 'high'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_get_text_blocks(self, page: fitz.Page) -> Dict[str, Any]:
        """get_text("blocks")メソッドの分析"""
        try:
            blocks = page.get_text("blocks")
            
            # 田中関連ブロックを検索
            tanaka_blocks = []
            for i, block_info in enumerate(blocks):
                if len(block_info) >= 5:  # テキストブロック
                    text = block_info[4]
                    if any(char in text for char in ['田', '中', '太', '郎', '朗']):
                        tanaka_blocks.append({
                            'index': i,
                            'text': text[:100],  # 最初の100文字
                            'bbox': [block_info[0], block_info[1], block_info[2], block_info[3]],
                            'block_type': block_info[5] if len(block_info) > 5 else 'text'
                        })
            
            return {
                'total_blocks': len(blocks),
                'tanaka_blocks_found': len(tanaka_blocks),
                'tanaka_blocks': tanaka_blocks,
                'sample_blocks': blocks[:3] if blocks else [],
                'data_structure': 'List[Tuple[x0, y0, x1, y1, text, block_type, ...]]',
                'pros': ['高速', 'ブロック構造明確', 'シンプル'],
                'cons': ['粒度が粗い', '文字・単語レベル座標なし'],
                'precision': 'low',
                'speed': 'very_high'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_get_text_dict(self, page: fitz.Page) -> Dict[str, Any]:
        """get_text("dict")メソッドの分析"""
        try:
            text_dict = page.get_text("dict")
            
            total_chars = 0
            tanaka_chars_found = 0
            tanaka_details = []
            
            # 階層構造を走査
            for block in text_dict.get('blocks', []):
                if 'lines' in block:
                    for line in block['lines']:
                        for span in line.get('spans', []):
                            text = span.get('text', '')
                            total_chars += len(text)
                            
                            # 田中関連文字をチェック
                            for i, char in enumerate(text):
                                if char in ['田', '中', '太', '郎', '朗']:
                                    tanaka_chars_found += 1
                                    tanaka_details.append({
                                        'char': char,
                                        'span_text': text,
                                        'span_bbox': span.get('bbox'),
                                        'font': span.get('font'),
                                        'size': span.get('size'),
                                        'char_index_in_span': i
                                    })
            
            return {
                'total_chars_estimated': total_chars,
                'tanaka_chars_found': tanaka_chars_found,
                'tanaka_details': tanaka_details[:10],  # 最初の10個
                'structure_depth': 'blocks -> lines -> spans',
                'data_structure': 'Dict with hierarchical structure',
                'pros': ['階層構造明確', 'フォント情報豊富', '構造化データ'],
                'cons': ['文字レベル座標なし', '複雑な走査必要'],
                'precision': 'medium',
                'speed': 'medium'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_get_text_rawdict(self, page: fitz.Page) -> Dict[str, Any]:
        """get_text("rawdict")メソッドの分析"""
        try:
            rawdict = page.get_text("rawdict")
            
            total_chars = 0
            tanaka_chars_found = 0
            tanaka_details = []
            
            # rawdictの階層構造を走査
            for block in rawdict.get('blocks', []):
                if 'lines' in block:
                    for line in block['lines']:
                        for span in line.get('spans', []):
                            chars = span.get('chars', [])
                            for char_info in chars:
                                total_chars += 1
                                char = char_info.get('c', '')
                                if char in ['田', '中', '太', '郎', '朗']:
                                    tanaka_chars_found += 1
                                    tanaka_details.append({
                                        'char': char,
                                        'bbox': char_info.get('bbox'),
                                        'origin': char_info.get('origin'),
                                        'font': span.get('font'),
                                        'size': span.get('size')
                                    })
            
            return {
                'total_chars': total_chars,
                'tanaka_chars_found': tanaka_chars_found,
                'tanaka_details': tanaka_details,
                'structure_depth': 'blocks -> lines -> spans -> chars',
                'data_structure': 'Dict with char-level bbox data',
                'pros': ['文字レベル座標', '完全な階層構造', '最も詳細'],
                'cons': ['データ量大', '処理時間長'],
                'precision': 'very_high',
                'speed': 'low'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_get_textpage_ocr(self, page: fitz.Page) -> Dict[str, Any]:
        """get_textpage_ocr()メソッドの分析"""
        try:
            # OCRメソッドは通常テッセラクトが必要
            textpage = page.get_textpage_ocr()
            
            return {
                'available': textpage is not None,
                'data_structure': 'TextPage object',
                'pros': ['OCR対応', 'スキャンPDF対応'],
                'cons': ['外部依存', '処理時間長', 'テッセラクト必要'],
                'precision': 'variable',
                'speed': 'very_low',
                'note': 'OCR機能、テッセラクト依存'
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'note': 'OCR機能利用不可（テッセラクト未インストールの可能性）'
            }
    
    def _analyze_search_for(self, page: fitz.Page) -> Dict[str, Any]:
        """search_for()メソッドの分析"""
        try:
            search_terms = ['田中太郎', '田中太朗', '田中', '太郎', '太朗']
            search_results = {}
            
            for term in search_terms:
                rects = page.search_for(term)
                if rects:
                    search_results[term] = [{
                        'bbox': [rect.x0, rect.y0, rect.x1, rect.y1]
                    } for rect in rects]
            
            return {
                'search_results': search_results,
                'total_matches': sum(len(results) for results in search_results.values()),
                'data_structure': 'List[fitz.Rect]',
                'pros': ['特定文字列検索', '高速', '矩形座標取得'],
                'cons': ['文字レベル座標なし', '既知文字列のみ'],
                'precision': 'high_for_known_strings',
                'speed': 'very_high'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_get_texttrace(self, page: fitz.Page) -> Dict[str, Any]:
        """get_texttrace()メソッドの分析"""
        try:
            # テキストトレース情報を取得
            texttrace = page.get_texttrace()
            
            return {
                'available': texttrace is not None,
                'data_size': len(texttrace) if texttrace else 0,
                'data_structure': 'List of trace information',
                'pros': ['低レベルテキスト情報', 'レンダリング詳細'],
                'cons': ['複雑な構造', '特殊用途', '解析困難'],
                'precision': 'very_high',
                'speed': 'low',
                'note': '低レベルテキストトレース情報'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def generate_comparison_report(self) -> str:
        """比較分析レポートを生成"""
        if not self.analysis_results:
            return "分析結果がありません"
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("PyMuPDF文字座標取得メソッド包括分析レポート")
        report_lines.append("=" * 80)
        report_lines.append(f"生成時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"対象ファイル: {self.pdf_path}")
        report_lines.append("")
        
        # サマリーテーブル
        report_lines.append("【メソッド比較サマリー】")
        report_lines.append("-" * 60)
        report_lines.append(f"{'メソッド名':<20} {'精度':<10} {'速度':<10} {'実行時間':<10}")
        report_lines.append("-" * 60)
        
        for method_name, result in self.analysis_results.items():
            if 'error' not in result:
                precision = result.get('precision', 'N/A')
                speed = result.get('speed', 'N/A')
                exec_time = f"{result.get('execution_time', 0):.3f}s" if result.get('execution_time') else 'N/A'
                report_lines.append(f"{method_name:<20} {precision:<10} {speed:<10} {exec_time:<10}")
            else:
                report_lines.append(f"{method_name:<20} {'ERROR':<10} {'N/A':<10} {'N/A':<10}")
        
        report_lines.append("")
        
        # 詳細分析
        report_lines.append("【詳細分析結果】")
        report_lines.append("")
        
        for method_name, result in self.analysis_results.items():
            report_lines.append(f"■ {method_name}")
            report_lines.append("-" * 40)
            
            if 'error' in result:
                report_lines.append(f"エラー: {result['error']}")
            else:
                if 'data_structure' in result:
                    report_lines.append(f"データ構造: {result['data_structure']}")
                
                if 'pros' in result:
                    report_lines.append(f"長所: {', '.join(result['pros'])}")
                
                if 'cons' in result:
                    report_lines.append(f"短所: {', '.join(result['cons'])}")
                
                if 'tanaka_chars_found' in result:
                    report_lines.append(f"田中関連文字検出数: {result['tanaka_chars_found']}")
                
                if 'tanaka_words_found' in result:
                    report_lines.append(f"田中関連単語検出数: {result['tanaka_words_found']}")
                
                if 'total_matches' in result:
                    report_lines.append(f"検索マッチ数: {result['total_matches']}")
                
                if 'execution_time' in result and result['execution_time']:
                    report_lines.append(f"実行時間: {result['execution_time']:.3f}秒")
                
                if 'note' in result:
                    report_lines.append(f"注記: {result['note']}")
            
            report_lines.append("")
        
        # 推奨事項
        report_lines.append("【改行を跨ぐPII対応のための推奨事項】")
        report_lines.append("-" * 60)
        
        # rawdictの分析結果をチェック
        rawdict_result = self.analysis_results.get('get_text_rawdict', {})
        chars_result = self.analysis_results.get('get_text_chars', {})
        
        if 'error' not in rawdict_result and rawdict_result.get('tanaka_chars_found', 0) > 0:
            report_lines.append("✅ 最推奨: get_text('rawdict')")
            report_lines.append("   - 文字レベル座標と階層構造の両方を提供")
            report_lines.append("   - 改行を跨ぐPII検出に最適")
            report_lines.append("   - 完全な座標マッピングが可能")
        
        if 'error' not in chars_result and chars_result.get('tanaka_chars_found', 0) > 0:
            report_lines.append("✅ 次善: get_text('chars')")
            report_lines.append("   - 文字レベル座標が正確")
            report_lines.append("   - 高速だが行・ブロック情報なし")
            report_lines.append("   - 座標マッピングに追加処理必要")
        
        words_result = self.analysis_results.get('get_text_words', {})
        if 'error' not in words_result:
            report_lines.append("⚠️  単語レベル: get_text('words')")
            report_lines.append("   - 高速だが文字レベル座標なし")
            report_lines.append("   - 改行を跨ぐPII検出には不適切")
        
        report_lines.append("")
        report_lines.append("【結論】")
        report_lines.append("改行を跨ぐPII検出にはget_text('rawdict')が最適")
        report_lines.append("文字レベル座標と階層構造の完全な情報を提供")
        
        return "\n".join(report_lines)

def main():
    """メイン実行関数"""
    test_pdf_path = "./test_japanese_linebreaks.pdf"
    
    if not os.path.exists(test_pdf_path):
        logger.error(f"テストファイルが見つかりません: {test_pdf_path}")
        return
    
    try:
        # 分析実行
        analyzer = FitzCoordinateMethodAnalyzer(test_pdf_path)
        results = analyzer.analyze_all_methods()
        
        # レポート生成
        report = analyzer.generate_comparison_report()
        
        # レポート保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"fitz_coordinate_methods_analysis_{timestamp}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # JSON詳細データ保存
        json_path = f"fitz_coordinate_methods_data_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"分析完了:")
        logger.info(f"  - レポート: {report_path}")
        logger.info(f"  - 詳細データ: {json_path}")
        
        # コンソール出力
        print("\n" + report)
        
    except Exception as e:
        logger.error(f"実行エラー: {e}")
        raise

if __name__ == "__main__":
    main()