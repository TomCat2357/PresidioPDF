#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PII検出結果の一文字ずつ座標詳細レポート生成
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
from config_manager import ConfigManager
from pdf_processor import PDFProcessor
from presidio_web_core import PresidioPDFWebApp

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PIICharacterCoordinateAnalyzer:
    """PII検出結果の文字レベル座標解析"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pdf_document = None
        self.web_app = None
        self.analysis_results = []
        
    def analyze_pii_coordinates(self) -> List[Dict]:
        """PII検出と文字レベル座標解析を実行"""
        try:
            logger.info(f"PII座標解析開始: {self.pdf_path}")
            
            # PresidioPDFWebAppを初期化
            session_id = "test_session"
            self.web_app = PresidioPDFWebApp(session_id, use_gpu=False)
            
            # PDFファイルを読み込み
            result = self.web_app.load_pdf_file(self.pdf_path)
            if not result['success']:
                raise Exception(f"PDF読み込みエラー: {result['message']}")
            
            # 個人情報検出を実行
            detection_result = self.web_app.run_detection()
            if not detection_result['success']:
                raise Exception(f"検出エラー: {detection_result['message']}")
            
            logger.info(f"検出完了: {len(detection_result['results'])}件のPII")
            
            # 各PIIについて文字レベル座標を解析
            for i, entity in enumerate(detection_result['results']):
                pii_analysis = self._analyze_single_pii(entity, i + 1)
                if pii_analysis:
                    self.analysis_results.append(pii_analysis)
            
            return self.analysis_results
            
        except Exception as e:
            logger.error(f"PII座標解析エラー: {e}")
            raise
        finally:
            if self.pdf_document:
                self.pdf_document.close()
    
    def _analyze_single_pii(self, entity: Dict, pii_index: int) -> Optional[Dict]:
        """単一PIIの文字レベル座標解析"""
        try:
            pii_text = entity.get('text', '')
            page_num = entity.get('page', 1)
            start_offset = entity.get('start', 0)
            end_offset = entity.get('end', 0)
            entity_type = entity.get('entity_type', 'UNKNOWN')
            
            logger.info(f"PII #{pii_index} 解析中: '{pii_text}' ({entity_type}) on page {page_num}")
            
            # PDFドキュメントを開く
            if not self.pdf_document:
                self.pdf_document = fitz.open(self.pdf_path)
            
            # ページインデックス（0-based）
            page_index = page_num - 1
            if page_index >= len(self.pdf_document):
                logger.warning(f"無効なページ番号: {page_num}")
                return None
            
            # 文字マッピングを構築
            page_mapping = self.web_app._build_character_offset_mapping(page_index)
            if not page_mapping:
                logger.warning(f"ページマッピング構築失敗: page {page_num}")
                return None
            
            # オフセット範囲の文字詳細を取得
            char_details = self._extract_character_details(
                page_mapping, start_offset, end_offset, pii_text
            )
            
            if not char_details:
                logger.warning(f"文字詳細取得失敗: '{pii_text}'")
                return None
            
            # 解析結果を構築
            analysis = {
                'pii_index': pii_index,
                'entity_type': entity_type,
                'text': pii_text,
                'page': page_num,
                'start_offset': start_offset,
                'end_offset': end_offset,
                'coordinates': entity.get('coordinates', {}),
                'line_rects': entity.get('line_rects', []),
                'character_count': len(char_details),
                'character_details': char_details,
                'analysis_summary': self._create_analysis_summary(char_details, pii_text)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"単一PII解析エラー: {e}")
            return None
    
    def _extract_character_details(self, page_mapping: Dict, start_offset: int, end_offset: int, pii_text: str) -> List[Dict]:
        """オフセット範囲の文字詳細を抽出"""
        try:
            char_positions = page_mapping['char_positions']
            char_details = []
            
            for i in range(start_offset, end_offset):
                if i < len(char_positions):
                    char_info = char_positions[i]
                    char_text = char_info['char']
                    bbox = char_info['bbox']
                    
                    detail = {
                        'char_index': i - start_offset,  # PII内での文字インデックス
                        'global_offset': i,  # 全体テキストでのオフセット
                        'character': char_text,
                        'bbox': bbox,
                        'has_coordinates': bbox is not None
                    }
                    
                    if bbox:
                        detail.update({
                            'x0': float(bbox[0]),
                            'y0': float(bbox[1]),
                            'x1': float(bbox[2]),
                            'y1': float(bbox[3]),
                            'width': float(bbox[2] - bbox[0]),
                            'height': float(bbox[3] - bbox[1])
                        })
                    
                    char_details.append(detail)
            
            return char_details
            
        except Exception as e:
            logger.error(f"文字詳細抽出エラー: {e}")
            return []
    
    def _create_analysis_summary(self, char_details: List[Dict], pii_text: str) -> Dict:
        """文字解析のサマリーを作成"""
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
            }
        }
        
        return summary
    
    def generate_reports(self, output_dir: str = "."):
        """詳細レポートを生成"""
        if not self.analysis_results:
            logger.warning("解析結果がありません。先にanalyze_pii_coordinates()を実行してください。")
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # テキストレポート生成
        text_report_path = os.path.join(output_dir, f"pii_character_report_{timestamp}.txt")
        self._generate_text_report(text_report_path)
        
        # JSONレポート生成
        json_report_path = os.path.join(output_dir, f"pii_character_data_{timestamp}.json")
        self._generate_json_report(json_report_path)
        
        # CSV座標データ生成
        csv_report_path = os.path.join(output_dir, f"pii_character_coordinates_{timestamp}.csv")
        self._generate_csv_report(csv_report_path)
        
        logger.info(f"レポート生成完了:")
        logger.info(f"  - テキスト: {text_report_path}")
        logger.info(f"  - JSON: {json_report_path}")
        logger.info(f"  - CSV: {csv_report_path}")
    
    def _generate_text_report(self, file_path: str):
        """テキスト形式の詳細レポート生成"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("PII検出結果 - 文字レベル座標詳細レポート\n")
            f.write("="*80 + "\n")
            f.write(f"生成時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"対象ファイル: {self.pdf_path}\n")
            f.write(f"検出PII数: {len(self.analysis_results)}\n")
            f.write("\n")
            
            for analysis in self.analysis_results:
                f.write("-"*60 + "\n")
                f.write(f"PII #{analysis['pii_index']}: {analysis['text']}\n")
                f.write("-"*60 + "\n")
                f.write(f"エンティティタイプ: {analysis['entity_type']}\n")
                f.write(f"ページ: {analysis['page']}\n")
                f.write(f"オフセット範囲: {analysis['start_offset']}-{analysis['end_offset']}\n")
                f.write(f"文字数: {analysis['character_count']}\n")
                
                # 全体座標
                coords = analysis['coordinates']
                if coords:
                    f.write(f"全体座標: ({coords.get('x0', 0):.3f}, {coords.get('y0', 0):.3f}) - ({coords.get('x1', 0):.3f}, {coords.get('y1', 0):.3f})\n")
                
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
    
    def _generate_json_report(self, file_path: str):
        """JSON形式のデータレポート生成"""
        report_data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'source_file': self.pdf_path,
                'total_pii_count': len(self.analysis_results)
            },
            'analysis_results': self.analysis_results
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    def _generate_csv_report(self, file_path: str):
        """CSV形式の座標データレポート生成"""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # ヘッダー
            writer.writerow([
                'PII_Index', 'Entity_Type', 'PII_Text', 'Page', 'Char_Index',
                'Character', 'Global_Offset', 'X0', 'Y0', 'X1', 'Y1',
                'Width', 'Height', 'Has_Coordinates'
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
                        char_detail['has_coordinates']
                    ]
                    writer.writerow(row)

def main():
    """メイン実行関数"""
    test_pdf_path = "./test_japanese_linebreaks.pdf"
    
    if not os.path.exists(test_pdf_path):
        logger.error(f"テストファイルが見つかりません: {test_pdf_path}")
        return
    
    try:
        # PII座標解析を実行
        analyzer = PIICharacterCoordinateAnalyzer(test_pdf_path)
        results = analyzer.analyze_pii_coordinates()
        
        logger.info(f"解析完了: {len(results)}件のPIIを解析")
        
        # レポート生成
        analyzer.generate_reports()
        
        # コンソールサマリー出力
        print("\n" + "="*60)
        print("PII文字レベル座標解析 - サマリー")
        print("="*60)
        for analysis in results:
            summary = analysis['analysis_summary']
            print(f"PII #{analysis['pii_index']}: '{analysis['text']}' ({analysis['entity_type']})")
            if 'error' not in summary:
                print(f"  文字数: {summary['total_characters']} (座標あり: {summary['characters_with_coordinates']})")
                bbox = summary['bounding_box']
                print(f"  境界: ({bbox['x0']:.2f}, {bbox['y0']:.2f}) - ({bbox['x1']:.2f}, {bbox['y1']:.2f})")
            else:
                print(f"  エラー: {summary['error']}")
            print()
        
    except Exception as e:
        logger.error(f"実行エラー: {e}")
        raise

if __name__ == "__main__":
    main()