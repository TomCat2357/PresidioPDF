#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座標ずれ問題の解析とテスト修正ツール
"""

import os
import sys
import json
import logging
from typing import List, Dict, Optional, Tuple
import fitz  # PyMuPDF

# プロジェクトモジュールをインポート
sys.path.append('src')
from config_manager import ConfigManager
from pdf_processor import PDFProcessor

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CoordinateAlignmentTester:
    """座標アライメント検証ツール"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pdf_document = None
        self.results = []
        
    def analyze_text_extraction_methods(self) -> Dict:
        """異なるテキスト抽出方式の比較分析"""
        try:
            self.pdf_document = fitz.open(self.pdf_path)
            page = self.pdf_document[0]  # 最初のページを分析
            
            print("="*80)
            print("テキスト抽出方式の比較分析")
            print("="*80)
            
            # 方式1: get_text() - プレーンテキスト（Presidioで使用）
            plain_text = page.get_text()
            print(f"方式1 - get_text(): {len(plain_text)}文字")
            print(f"内容: {repr(plain_text[:100])}...")
            print()
            
            # 方式2: get_text("rawdict") - 座標特定で使用
            textpage = page.get_textpage()
            raw_data = json.loads(textpage.extractRAWJSON())
            
            # rawdictから再構築されるテキスト
            reconstructed_text = self._reconstruct_text_from_rawdict(raw_data)
            print(f"方式2 - rawdict再構築: {len(reconstructed_text)}文字")
            print(f"内容: {repr(reconstructed_text[:100])}...")
            print()
            
            # 方式3: PDF processorでPDFTextLocatorを使用
            from pdf_locator import PDFTextLocator
            doc = fitz.open(self.pdf_path)
            locator = PDFTextLocator(doc)
            processor_text = locator.full_text
            processor_text_no_newlines = locator.full_text_no_newlines
            doc.close()
            
            print(f"方式3 - PDF locator (通常): {len(processor_text)}文字")
            print(f"内容: {repr(processor_text[:100])}...")
            print()
            
            print(f"方式3 - PDF locator (改行なし): {len(processor_text_no_newlines)}文字")
            print(f"内容: {repr(processor_text_no_newlines[:100])}...")
            print()
            
            # 差異分析
            print("【差異分析】")
            if plain_text != reconstructed_text:
                print("❌ プレーンテキストとrawdict再構築テキストが不一致")
                self._compare_texts("プレーンテキスト", plain_text, "rawdict再構築", reconstructed_text)
            else:
                print("✅ プレーンテキストとrawdict再構築テキストが一致")
            
            if plain_text != processor_text:
                print("❌ プレーンテキストとPDF locator (通常)が不一致")
                self._compare_texts("プレーンテキスト", plain_text, "PDF locator", processor_text)
            else:
                print("✅ プレーンテキストとPDF locator (通常)が一致")
            
            # Presidioで使用される改行なしテキストの比較
            presidio_text = processor_text_no_newlines
            print(f"\n【Presidio解析用テキスト】改行なし版: {len(presidio_text)}文字")
            
            return {
                'plain_text': plain_text,
                'reconstructed_text': reconstructed_text,
                'processor_text': processor_text,
                'presidio_text': presidio_text,
                'alignment_ok': plain_text == reconstructed_text == processor_text
            }
            
        except Exception as e:
            logger.error(f"テキスト抽出分析エラー: {e}")
            raise
        finally:
            if self.pdf_document:
                self.pdf_document.close()
    
    def _reconstruct_text_from_rawdict(self, raw_data: Dict) -> str:
        """rawdictデータからテキストを再構築（座標特定方式と同じロジック）"""
        full_text = ''
        
        for block in raw_data['blocks']:
            for line in block['lines']:
                for span in line['spans']:
                    for char_data in span['chars']:
                        full_text += char_data['c']
                # 行末に改行を追加
                full_text += '\n'
        
        return full_text
    
    def _compare_texts(self, name1: str, text1: str, name2: str, text2: str):
        """2つのテキストの詳細比較"""
        print(f"\n【{name1} vs {name2}】")
        print(f"{name1}長さ: {len(text1)}")
        print(f"{name2}長さ: {len(text2)}")
        
        # 文字レベル比較（最初の50文字）
        max_compare = min(50, len(text1), len(text2))
        for i in range(max_compare):
            if i < len(text1) and i < len(text2):
                if text1[i] != text2[i]:
                    print(f"  差異 [{i:2d}]: '{text1[i]}' (ord:{ord(text1[i])}) != '{text2[i]}' (ord:{ord(text2[i])})")
                    break
    
    def test_pii_offset_mapping(self) -> List[Dict]:
        """PII検出オフセットのマッピング精度をテスト"""
        try:
            print("="*80)
            print("PII検出オフセットマッピング精度テスト")
            print("="*80)
            
            # PDF Processorでの実際の検出を実行
            config_manager = ConfigManager()
            processor = PDFProcessor(config_manager)
            
            # PDF解析実行
            entities = processor.analyze_pdf(self.pdf_path)
            print(f"検出されたPII: {len(entities)}件")
            
            # 各PIIについて座標マッピングを検証
            self.pdf_document = fitz.open(self.pdf_path)
            page = self.pdf_document[0]
            
            # PDFTextLocatorを使用（実際の処理と同じ方式）
            from pdf_locator import PDFTextLocator
            locator = PDFTextLocator(self.pdf_document)
            
            # Presidio解析用の改行なしテキスト
            presidio_text = locator.full_text_no_newlines
            print(f"Presidio解析用テキスト: {len(presidio_text)}文字")
            
            # 通常のテキスト（座標マッピング用）
            full_text = locator.full_text
            char_mapping = locator.char_data  # PDFTextLocatorの文字データ
            
            verification_results = []
            
            for i, entity in enumerate(entities[:5], 1):  # 最初の5件をテスト
                print(f"\n【PII #{i}: {entity['text']}】")
                print(f"エンティティタイプ: {entity['entity_type']}")
                print(f"オフセット: {entity['start']}-{entity['end']}")
                
                # オフセット範囲のテキスト抽出（Presidio解析用テキストから）
                start, end = entity['start'], entity['end']
                if end <= len(presidio_text):
                    extracted_text = presidio_text[start:end]
                    print(f"抽出テキスト (Presidio): '{extracted_text}'")
                    print(f"期待テキスト: '{entity['text']}'")
                    
                    # テキスト一致チェック
                    text_match = extracted_text == entity['text']
                    print(f"テキスト一致: {'✅' if text_match else '❌'}")
                    
                    # 座標マッピング検証（改行なしオフセットを使用）
                    coord_results = locator.locate_pii_by_offset_no_newlines(start, end)
                    if coord_results:
                        first_rect = coord_results[0]
                        print(f"座標結果: ({first_rect.x0:.2f}, {first_rect.y0:.2f}) - ({first_rect.x1:.2f}, {first_rect.y1:.2f})")
                        print(f"矩形数: {len(coord_results)}")
                        
                        # 検索による座標取得（比較用）
                        search_rects = page.search_for(entity['text'])
                        if search_rects:
                            search_bbox = search_rects[0]
                            print(f"検索座標: ({search_bbox.x0:.2f}, {search_bbox.y0:.2f}) - ({search_bbox.x1:.2f}, {search_bbox.y1:.2f})")
                            
                            # 座標差計算
                            coord_diff = abs(first_rect.x0 - search_bbox.x0) + abs(first_rect.y0 - search_bbox.y0)
                            print(f"座標差: {coord_diff:.2f}ピクセル")
                        
                        verification_results.append({
                            'pii_text': entity['text'],
                            'text_match': text_match,
                            'extracted_text': extracted_text,
                            'locator_coords': {'x0': first_rect.x0, 'y0': first_rect.y0, 'x1': first_rect.x1, 'y1': first_rect.y1},
                            'rect_count': len(coord_results)
                        })
                    else:
                        print("❌ 座標マッピング失敗")
                else:
                    print("❌ オフセット範囲がテキスト長を超過")
            
            return verification_results
            
        except Exception as e:
            logger.error(f"PII オフセットマッピングテストエラー: {e}")
            raise
        finally:
            if self.pdf_document:
                self.pdf_document.close()
    
    def _build_char_mapping_correct(self, raw_data: Dict) -> List[Dict]:
        """正確な文字マッピングを構築"""
        char_mapping = []
        char_index = 0
        
        for block in raw_data['blocks']:
            for line in block['lines']:
                for span in line['spans']:
                    for char_data in span['chars']:
                        char_mapping.append({
                            'offset': char_index,
                            'char': char_data['c'],
                            'bbox': char_data['bbox']
                        })
                        char_index += 1
                
                # 行末改行
                char_mapping.append({
                    'offset': char_index,
                    'char': '\n',
                    'bbox': None
                })
                char_index += 1
        
        return char_mapping
    
    def generate_fix_recommendations(self) -> Dict:
        """修正推奨事項を生成"""
        print("="*80)
        print("修正推奨事項")
        print("="*80)
        
        recommendations = {
            'text_sync_fix': {
                'description': 'Presidio用テキストとrawdict再構築テキストの同期を修正',
                'action': 'PDFProcessor._extract_text_with_positions()メソッドを修正してrawdict方式に統一'
            },
            'offset_calculation_fix': {
                'description': 'オフセット計算の精度向上',
                'action': '改行・空白の挿入ロジックを統一して座標マッピングの精度を向上'
            },
            'coordinate_mapping_fix': {
                'description': '座標マッピングアルゴリズムの改善',
                'action': 'presidio_web_core.py の _locate_pii_by_offset_precise() を改善'
            }
        }
        
        for key, rec in recommendations.items():
            print(f"【{rec['description']}】")
            print(f"対策: {rec['action']}")
            print()
        
        return recommendations

def main():
    """メイン実行関数"""
    test_pdf_path = "./test_japanese_linebreaks.pdf"
    
    if not os.path.exists(test_pdf_path):
        logger.error(f"テストファイルが見つかりません: {test_pdf_path}")
        return
    
    try:
        tester = CoordinateAlignmentTester(test_pdf_path)
        
        # テキスト抽出方式の比較
        text_analysis = tester.analyze_text_extraction_methods()
        
        # PII オフセットマッピングテスト
        mapping_results = tester.test_pii_offset_mapping()
        
        # 修正推奨事項の生成
        recommendations = tester.generate_fix_recommendations()
        
        # 結果サマリー
        print("="*80)
        print("座標アライメント検証結果サマリー")
        print("="*80)
        print(f"テキスト同期状態: {'✅ 正常' if text_analysis['alignment_ok'] else '❌ 不整合'}")
        print(f"検証したPII数: {len(mapping_results)}")
        
        text_match_count = sum(1 for r in mapping_results if r['text_match'])
        print(f"テキスト一致率: {text_match_count}/{len(mapping_results)} ({text_match_count/len(mapping_results)*100:.1f}%)")
        
        if not text_analysis['alignment_ok']:
            print("\n⚠️ テキスト同期の問題が座標ずれの原因です")
            print("修正が必要: presidio_web_core.py と PDF processor の同期ロジック")
        
    except Exception as e:
        logger.error(f"実行エラー: {e}")
        raise

if __name__ == "__main__":
    main()