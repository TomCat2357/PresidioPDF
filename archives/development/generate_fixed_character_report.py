#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正後の文字レベル座標詳細レポート生成
pii_character_report_20250629_232913.txt と同形式で出力
"""

import os
import sys
import json
import csv
import logging
from datetime import datetime
from typing import List, Dict, Optional
import fitz  # PyMuPDF

# プロジェクトモジュールをインポート
sys.path.append('src')
from presidio_web_core import PresidioPDFWebApp
from pdf_locator import PDFTextLocator

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FixedCharacterReportGenerator:
    """修正後の文字レベル座標詳細レポート生成"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pdf_document = None
        self.web_app = None
        self.analysis_results = []
        
    def generate_detailed_analysis(self) -> List[Dict]:
        """修正後のシステムで詳細な文字レベル解析を実行"""
        try:
            logger.info(f"修正後システムでPII座標解析開始: {self.pdf_path}")
            
            # PresidioPDFWebAppを初期化（修正後）
            session_id = "fixed_analysis"
            self.web_app = PresidioPDFWebApp(session_id, use_gpu=False)
            
            # PDFファイルを読み込み
            result = self.web_app.load_pdf_file(self.pdf_path)
            if not result['success']:
                raise Exception(f"PDF読み込みエラー: {result['message']}")
            
            # 個人情報検出を実行（修正後システム）
            detection_result = self.web_app.run_detection()
            if not detection_result['success']:
                raise Exception(f"検出エラー: {detection_result['message']}")
            
            detected_entities = detection_result['results']
            logger.info(f"修正後システムで検出完了: {len(detected_entities)}件のPII")
            
            # PDFTextLocatorで詳細解析
            self.pdf_document = fitz.open(self.pdf_path)
            locator = PDFTextLocator(self.pdf_document)
            
            # 各PIIについて文字レベル座標を解析
            for i, entity in enumerate(detected_entities):
                pii_analysis = self._analyze_single_pii_fixed(entity, locator, i + 1)
                if pii_analysis:
                    self.analysis_results.append(pii_analysis)
            
            return self.analysis_results
            
        except Exception as e:
            logger.error(f"修正後PII座標解析エラー: {e}")
            raise
        finally:
            if self.pdf_document:
                self.pdf_document.close()
    
    def _analyze_single_pii_fixed(self, entity: Dict, locator: PDFTextLocator, pii_index: int) -> Optional[Dict]:
        """修正後システムでの単一PII文字レベル座標解析"""
        try:
            pii_text = entity.get('text', '')
            page_num = entity.get('page', 1)
            start_offset = entity.get('start', 0)
            end_offset = entity.get('end', 0)
            entity_type = entity.get('entity_type', 'UNKNOWN')
            
            logger.info(f"PII #{pii_index} 解析中: '{pii_text}' ({entity_type}) on page {page_num}")
            
            # 修正後システム：改行なしオフセット座標特定を使用
            coord_rects = locator.locate_pii_by_offset_no_newlines(start_offset, end_offset)
            
            if not coord_rects:
                logger.warning(f"修正後システムでも座標特定失敗: '{pii_text}'")
                return None
            
            # メイン座標（最初の矩形）
            main_rect = coord_rects[0]
            main_coordinates = {
                'x0': float(main_rect.x0),
                'y0': float(main_rect.y0),
                'x1': float(main_rect.x1),
                'y1': float(main_rect.y1)
            }
            
            # 改行なしテキストから文字詳細を取得
            presidio_text = locator.full_text_no_newlines
            if end_offset <= len(presidio_text):
                extracted_text = presidio_text[start_offset:end_offset]
            else:
                extracted_text = pii_text  # フォールバック
            
            # 文字レベル詳細座標を構築（推定）
            char_details = self._build_character_details_from_rects(
                extracted_text, coord_rects, start_offset
            )
            
            # line_rects を構築
            line_rects = []
            for i, rect in enumerate(coord_rects):
                line_rects.append({
                    'rect': {
                        'x0': float(rect.x0),
                        'y0': float(rect.y0),
                        'x1': float(rect.x1),
                        'y1': float(rect.y1)
                    },
                    'text': extracted_text if i == 0 else f"part_{i+1}",
                    'line_number': i + 1
                })
            
            # 解析結果を構築
            analysis = {
                'pii_index': pii_index,
                'entity_type': entity_type,
                'text': pii_text,
                'page': page_num,
                'start_offset': start_offset,
                'end_offset': end_offset,
                'coordinates': main_coordinates,
                'line_rects': line_rects,
                'character_count': len(char_details),
                'character_details': char_details,
                'analysis_summary': self._create_analysis_summary_fixed(char_details, pii_text),
                'system_version': 'fixed',
                'extraction_method': 'PDFTextLocator.locate_pii_by_offset_no_newlines'
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"修正後単一PII解析エラー: {e}")
            return None
    
    def _build_character_details_from_rects(self, text: str, coord_rects: List, start_offset: int) -> List[Dict]:
        """座標矩形から文字詳細を推定構築"""
        char_details = []
        
        if not coord_rects:
            return char_details
        
        # 単純化：テキストの各文字に座標を均等分割で割り当て
        for i, char in enumerate(text):
            # 複数矩形がある場合は最初の矩形を使用（簡略化）
            rect = coord_rects[0] if coord_rects else None
            
            if rect and char != '\n':
                # 文字幅を推定（矩形幅をテキスト長で割る）
                char_width = (rect.x1 - rect.x0) / max(len(text.replace('\n', '')), 1)
                char_x0 = rect.x0 + (i * char_width)
                char_x1 = char_x0 + char_width
                
                detail = {
                    'char_index': i,
                    'global_offset': start_offset + i,
                    'character': char,
                    'bbox': [char_x0, rect.y0, char_x1, rect.y1],
                    'has_coordinates': True,
                    'x0': char_x0,
                    'y0': rect.y0,
                    'x1': char_x1,
                    'y1': rect.y1,
                    'width': char_width,
                    'height': rect.y1 - rect.y0
                }
            else:
                # 改行や座標なしの文字
                detail = {
                    'char_index': i,
                    'global_offset': start_offset + i,
                    'character': char,
                    'bbox': None,
                    'has_coordinates': False
                }
            
            char_details.append(detail)
        
        return char_details
    
    def _create_analysis_summary_fixed(self, char_details: List[Dict], pii_text: str) -> Dict:
        """修正後システムの解析サマリーを作成"""
        valid_chars = [c for c in char_details if c['has_coordinates']]
        
        if not valid_chars:
            return {'error': '有効な座標を持つ文字がありません'}
        
        # 座標統計
        x0_values = [c['x0'] for c in valid_chars]
        y0_values = [c['y0'] for c in valid_chars]
        x1_values = [c['x1'] for c in valid_chars]
        y1_values = [c['y1'] for c in valid_chars]
        
        summary = {
            'total_characters': len(char_details),
            'characters_with_coordinates': len(valid_chars),
            'characters_without_coordinates': len(char_details) - len(valid_chars),
            'bounding_box': {
                'x0': min(x0_values),
                'y0': min(y0_values),
                'x1': max(x1_values),
                'y1': max(y1_values)
            },
            'character_spacing': {
                'avg_width': sum(c['width'] for c in valid_chars) / len(valid_chars),
                'avg_height': sum(c['height'] for c in valid_chars) / len(valid_chars),
                'min_width': min(c['width'] for c in valid_chars),
                'max_width': max(c['width'] for c in valid_chars)
            },
            'system_version': 'fixed_with_PDFTextLocator'
        }
        
        return summary
    
    def generate_detailed_report(self, output_dir: str = "."):
        """pii_character_report_20250629_232913.txt と同形式の詳細レポート生成"""
        if not self.analysis_results:
            logger.warning("解析結果がありません。先にgenerate_detailed_analysis()を実行してください。")
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # テキストレポート生成
        text_report_path = os.path.join(output_dir, f"pii_character_report_fixed_{timestamp}.txt")
        self._generate_text_report_fixed(text_report_path)
        
        # JSONレポート生成
        json_report_path = os.path.join(output_dir, f"pii_character_data_fixed_{timestamp}.json")
        self._generate_json_report_fixed(json_report_path)
        
        # CSV座標データ生成
        csv_report_path = os.path.join(output_dir, f"pii_character_coordinates_fixed_{timestamp}.csv")
        self._generate_csv_report_fixed(csv_report_path)
        
        logger.info(f"修正後レポート生成完了:")
        logger.info(f"  - テキスト: {text_report_path}")
        logger.info(f"  - JSON: {json_report_path}")
        logger.info(f"  - CSV: {csv_report_path}")
    
    def _generate_text_report_fixed(self, file_path: str):
        """修正後システム版の詳細テキストレポート生成"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("PII検出結果 - 文字レベル座標詳細レポート（修正後システム）\n")
            f.write("="*80 + "\n")
            f.write(f"生成時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"対象ファイル: {self.pdf_path}\n")
            f.write(f"検出PII数: {len(self.analysis_results)}\n")
            f.write(f"システムバージョン: 修正後（PDFTextLocator統合）\n")
            f.write("\n")
            
            for analysis in self.analysis_results:
                f.write("-"*60 + "\n")
                f.write(f"PII #{analysis['pii_index']}: {analysis['text']}\n")
                f.write("-"*60 + "\n")
                f.write(f"エンティティタイプ: {analysis['entity_type']}\n")
                f.write(f"ページ: {analysis['page']}\n")
                f.write(f"オフセット範囲: {analysis['start_offset']}-{analysis['end_offset']}\n")
                f.write(f"文字数: {analysis['character_count']}\n")
                f.write(f"抽出方法: {analysis['extraction_method']}\n")
                
                # 全体座標
                coords = analysis['coordinates']
                f.write(f"全体座標: ({coords['x0']:.3f}, {coords['y0']:.3f}) - ({coords['x1']:.3f}, {coords['y1']:.3f})\n")
                
                # 解析サマリー
                summary = analysis['analysis_summary']
                if 'error' not in summary:
                    bbox = summary['bounding_box']
                    f.write(f"境界矩形: ({bbox['x0']:.3f}, {bbox['y0']:.3f}) - ({bbox['x1']:.3f}, {bbox['y1']:.3f})\n")
                    f.write(f"有効文字数: {summary['characters_with_coordinates']}/{summary['total_characters']}\n")
                
                f.write("\n文字別座標詳細:\n")
                for char_detail in analysis['character_details']:
                    char = char_detail['character']
                    if char == '\n':
                        char = '\\n'
                    elif char == '\r':
                        char = '\\r'
                    
                    f.write(f"  [{char_detail['char_index']:2d}] '{char}' ")
                    if char_detail['has_coordinates']:
                        f.write(f"座標: ({char_detail['x0']:6.2f}, {char_detail['y0']:6.2f}) - ({char_detail['x1']:6.2f}, {char_detail['y1']:6.2f}) ")
                        f.write(f"サイズ: {char_detail['width']:5.2f}×{char_detail['height']:5.2f}")
                    else:
                        f.write("座標なし")
                    f.write(f" (offset: {char_detail['global_offset']})\n")
                
                f.write("\n")
    
    def _generate_json_report_fixed(self, file_path: str):
        """修正後システム版のJSONレポート生成"""
        report_data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'source_file': self.pdf_path,
                'total_pii_count': len(self.analysis_results),
                'system_version': 'fixed_with_PDFTextLocator',
                'description': '修正後システムによる文字レベル座標解析結果'
            },
            'analysis_results': self.analysis_results
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    def _generate_csv_report_fixed(self, file_path: str):
        """修正後システム版のCSVレポート生成"""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # ヘッダー
            writer.writerow([
                'PII_Index', 'Entity_Type', 'PII_Text', 'Page', 'Char_Index',
                'Character', 'Global_Offset', 'X0', 'Y0', 'X1', 'Y1',
                'Width', 'Height', 'Has_Coordinates', 'System_Version'
            ])
            
            # データ行
            for analysis in self.analysis_results:
                for char_detail in analysis['character_details']:
                    char = char_detail['character']
                    if char == '\n':
                        char = '\\n'
                    elif char == '\r':
                        char = '\\r'
                    
                    row = [
                        analysis['pii_index'],
                        analysis['entity_type'],
                        analysis['text'],
                        analysis['page'],
                        char_detail['char_index'],
                        char,
                        char_detail['global_offset'],
                        char_detail.get('x0', ''),
                        char_detail.get('y0', ''),
                        char_detail.get('x1', ''),
                        char_detail.get('y1', ''),
                        char_detail.get('width', ''),
                        char_detail.get('height', ''),
                        char_detail['has_coordinates'],
                        'fixed'
                    ]
                    writer.writerow(row)

def main():
    """メイン実行関数"""
    test_pdf_path = "./test_japanese_linebreaks.pdf"
    
    if not os.path.exists(test_pdf_path):
        logger.error(f"テストファイルが見つかりません: {test_pdf_path}")
        return
    
    try:
        # 修正後システムでPII座標解析を実行
        generator = FixedCharacterReportGenerator(test_pdf_path)
        results = generator.generate_detailed_analysis()
        
        logger.info(f"修正後システム解析完了: {len(results)}件のPIIを解析")
        
        # 詳細レポート生成
        generator.generate_detailed_report()
        
        # コンソールサマリー出力
        print("\n" + "="*60)
        print("修正後システム - PII文字レベル座標解析サマリー")
        print("="*60)
        for analysis in results:
            summary = analysis['analysis_summary']
            print(f"PII #{analysis['pii_index']}: '{analysis['text']}' ({analysis['entity_type']})")
            if 'error' not in summary:
                print(f"  文字数: {summary['total_characters']} (座標あり: {summary['characters_with_coordinates']})")
                bbox = summary['bounding_box']
                print(f"  境界: ({bbox['x0']:.2f}, {bbox['y0']:.2f}) - ({bbox['x1']:.2f}, {bbox['y1']:.2f})")
                print(f"  システム: {summary['system_version']}")
            else:
                print(f"  エラー: {summary['error']}")
            print()
        
    except Exception as e:
        logger.error(f"実行エラー: {e}")
        raise

if __name__ == "__main__":
    main()