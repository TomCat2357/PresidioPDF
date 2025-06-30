#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真の文字レベル座標詳細レポート生成（改行を跨ぐ文字の正確な座標を反映）
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

class AccurateCharacterReportGenerator:
    """改行を跨ぐ文字の正確な座標を反映した文字レベル詳細レポート生成"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pdf_document = None
        self.web_app = None
        self.analysis_results = []
        
    def generate_accurate_analysis(self) -> List[Dict]:
        """改行を跨ぐ文字の正確な座標を取得する詳細解析を実行"""
        try:
            logger.info(f"正確な文字座標解析開始: {self.pdf_path}")
            
            # PresidioPDFWebAppを初期化
            session_id = "accurate_analysis"
            self.web_app = PresidioPDFWebApp(session_id, use_gpu=False)
            
            # PDFファイルを読み込み
            result = self.web_app.load_pdf_file(self.pdf_path)
            if not result['success']:
                raise Exception(f"PDF読み込みエラー: {result['message']}")
            
            # 個人情報検出を実行
            detection_result = self.web_app.run_detection()
            if not detection_result['success']:
                raise Exception(f"検出エラー: {detection_result['message']}")
            
            detected_entities = detection_result['results']
            logger.info(f"検出完了: {len(detected_entities)}件のPII")
            
            # PDFTextLocatorで正確な文字マッピングを構築
            self.pdf_document = fitz.open(self.pdf_path)
            locator = PDFTextLocator(self.pdf_document)
            
            # 各PIIについて正確な文字レベル座標を解析
            for i, entity in enumerate(detected_entities):
                pii_analysis = self._analyze_pii_with_accurate_chars(entity, locator, i + 1)
                if pii_analysis:
                    self.analysis_results.append(pii_analysis)
            
            return self.analysis_results
            
        except Exception as e:
            logger.error(f"正確な文字座標解析エラー: {e}")
            raise
        finally:
            if self.pdf_document:
                self.pdf_document.close()
    
    def _analyze_pii_with_accurate_chars(self, entity: Dict, locator: PDFTextLocator, pii_index: int) -> Optional[Dict]:
        """改行を跨ぐ文字の正確な座標を反映したPII解析"""
        try:
            pii_text = entity.get('text', '')
            page_num = entity.get('page', 1)
            start_offset = entity.get('start', 0)
            end_offset = entity.get('end', 0)
            entity_type = entity.get('entity_type', 'UNKNOWN')
            
            logger.info(f"PII #{pii_index} 正確な文字解析: '{pii_text}' ({entity_type})")
            
            # PDFTextLocatorから座標矩形を取得
            coord_rects = locator.locate_pii_by_offset_no_newlines(start_offset, end_offset)
            
            if not coord_rects:
                logger.warning(f"座標特定失敗: '{pii_text}'")
                return None
            
            # PDFTextLocatorのchar_dataから実際の文字座標を取得
            accurate_char_details = self._extract_accurate_character_coordinates(
                locator, start_offset, end_offset, pii_text
            )
            
            if not accurate_char_details:
                logger.warning(f"正確な文字座標取得失敗: '{pii_text}'")
                return None
            
            # メイン座標計算（有効文字の境界矩形）
            valid_chars = [c for c in accurate_char_details if c['has_coordinates']]
            if valid_chars:
                all_x0 = [c['x0'] for c in valid_chars]
                all_y0 = [c['y0'] for c in valid_chars]
                all_x1 = [c['x1'] for c in valid_chars]
                all_y1 = [c['y1'] for c in valid_chars]
                
                main_coordinates = {
                    'x0': float(min(all_x0)),
                    'y0': float(min(all_y0)),
                    'x1': float(max(all_x1)),
                    'y1': float(max(all_y1))
                }
            else:
                main_coordinates = {
                    'x0': float(coord_rects[0].x0),
                    'y0': float(coord_rects[0].y0),
                    'x1': float(coord_rects[0].x1),
                    'y1': float(coord_rects[0].y1)
                }
            
            # line_rects構築
            line_rects = []
            for i, rect in enumerate(coord_rects):
                line_rects.append({
                    'rect': {
                        'x0': float(rect.x0),
                        'y0': float(rect.y0),
                        'x1': float(rect.x1),
                        'y1': float(rect.y1)
                    },
                    'text': pii_text if i == 0 else f"line_{i+1}",
                    'line_number': i + 1
                })
            
            # 解析結果構築
            analysis = {
                'pii_index': pii_index,
                'entity_type': entity_type,
                'text': pii_text,
                'page': page_num,
                'start_offset': start_offset,
                'end_offset': end_offset,
                'coordinates': main_coordinates,
                'line_rects': line_rects,
                'character_count': len(accurate_char_details),
                'character_details': accurate_char_details,
                'analysis_summary': self._create_accurate_summary(accurate_char_details, pii_text),
                'system_version': 'accurate_character_mapping',
                'extraction_method': 'PDFTextLocator.char_data_direct_mapping'
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"正確な文字解析エラー: {e}")
            return None
    
    def _extract_accurate_character_coordinates(self, locator: PDFTextLocator, start_offset: int, end_offset: int, pii_text: str) -> List[Dict]:
        """PDFTextLocatorのchar_dataから正確な文字座標を抽出"""
        try:
            char_data = locator.char_data
            presidio_text = locator.full_text_no_newlines
            
            # 改行なしテキストでのオフセット範囲をchar_dataの改行ありオフセットにマッピング
            char_details = []
            
            # 改行なしテキストから改行ありテキストへのマッピングを構築
            no_newlines_to_char_data_mapping = self._build_offset_mapping(locator)
            
            # PII文字を一文字ずつ処理
            presidio_pii_text = presidio_text[start_offset:end_offset] if end_offset <= len(presidio_text) else pii_text
            
            for i, char in enumerate(presidio_pii_text):
                char_index_in_pii = i
                global_no_newlines_offset = start_offset + i
                
                # 改行なしオフセットから改行ありオフセットにマッピング
                char_data_offset = no_newlines_to_char_data_mapping.get(global_no_newlines_offset)
                
                detail = {
                    'char_index': char_index_in_pii,
                    'global_offset': global_no_newlines_offset,
                    'char_data_offset': char_data_offset,
                    'character': char,
                    'has_coordinates': False,
                    'bbox': None
                }
                
                # char_dataから実際の座標を取得
                if char_data_offset is not None and char_data_offset < len(char_data):
                    char_info = char_data[char_data_offset]
                    if char_info.get('char') == char and char_info.get('bbox'):
                        bbox = char_info['bbox']
                        detail.update({
                            'has_coordinates': True,
                            'bbox': bbox,
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
            
            logger.debug(f"正確な文字座標抽出完了: '{pii_text}' -> {len([c for c in char_details if c['has_coordinates']])}文字")
            return char_details
            
        except Exception as e:
            logger.error(f"正確な文字座標抽出エラー: {e}")
            return []
    
    def _build_offset_mapping(self, locator: PDFTextLocator) -> Dict[int, int]:
        """改行なしオフセットから改行ありchar_dataオフセットへのマッピングを構築"""
        try:
            char_data = locator.char_data
            full_text = locator.full_text
            no_newlines_text = locator.full_text_no_newlines
            
            mapping = {}
            no_newlines_pos = 0
            
            for char_data_pos, char_info in enumerate(char_data):
                char = char_info.get('char', '')
                
                # 改行や空白以外の文字の場合
                if char != '\n' and char.strip():
                    if no_newlines_pos < len(no_newlines_text) and no_newlines_text[no_newlines_pos] == char:
                        mapping[no_newlines_pos] = char_data_pos
                        no_newlines_pos += 1
                elif char.strip():  # 空白でない文字
                    if no_newlines_pos < len(no_newlines_text) and no_newlines_text[no_newlines_pos] == char:
                        mapping[no_newlines_pos] = char_data_pos
                        no_newlines_pos += 1
            
            logger.debug(f"オフセットマッピング構築完了: {len(mapping)}件")
            return mapping
            
        except Exception as e:
            logger.error(f"オフセットマッピング構築エラー: {e}")
            return {}
    
    def _create_accurate_summary(self, char_details: List[Dict], pii_text: str) -> Dict:
        """正確な文字解析のサマリーを作成"""
        valid_chars = [c for c in char_details if c['has_coordinates']]
        
        if not valid_chars:
            return {'error': '有効な座標を持つ文字がありません'}
        
        # 座標統計
        x0_values = [c['x0'] for c in valid_chars]
        y0_values = [c['y0'] for c in valid_chars]
        x1_values = [c['x1'] for c in valid_chars]
        y1_values = [c['y1'] for c in valid_chars]
        
        # 行別分布を分析
        line_distribution = {}
        for char in valid_chars:
            line_num = char.get('line', 0)
            if line_num not in line_distribution:
                line_distribution[line_num] = []
            line_distribution[line_num].append(char)
        
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
            'line_distribution': {
                'total_lines': len(line_distribution),
                'chars_per_line': {str(line): len(chars) for line, chars in line_distribution.items()}
            },
            'system_version': 'accurate_character_mapping'
        }
        
        return summary
    
    def generate_accurate_reports(self, output_dir: str = "."):
        """正確な文字座標を反映した詳細レポートを生成"""
        if not self.analysis_results:
            logger.warning("解析結果がありません。先にgenerate_accurate_analysis()を実行してください。")
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # テキストレポート生成
        text_report_path = os.path.join(output_dir, f"pii_character_report_accurate_{timestamp}.txt")
        self._generate_accurate_text_report(text_report_path)
        
        # JSONレポート生成
        json_report_path = os.path.join(output_dir, f"pii_character_data_accurate_{timestamp}.json")
        self._generate_accurate_json_report(json_report_path)
        
        # CSV座標データ生成
        csv_report_path = os.path.join(output_dir, f"pii_character_coordinates_accurate_{timestamp}.csv")
        self._generate_accurate_csv_report(csv_report_path)
        
        logger.info(f"正確な文字座標レポート生成完了:")
        logger.info(f"  - テキスト: {text_report_path}")
        logger.info(f"  - JSON: {json_report_path}")
        logger.info(f"  - CSV: {csv_report_path}")
    
    def _generate_accurate_text_report(self, file_path: str):
        """正確な文字座標を反映したテキストレポート生成"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("PII検出結果 - 正確な文字レベル座標詳細レポート（改行対応）\n")
            f.write("="*80 + "\n")
            f.write(f"生成時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"対象ファイル: {self.pdf_path}\n")
            f.write(f"検出PII数: {len(self.analysis_results)}\n")
            f.write(f"システムバージョン: 正確な文字マッピング（改行を跨ぐ文字対応）\n")
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
                    
                    line_dist = summary['line_distribution']
                    f.write(f"行分布: {line_dist['total_lines']}行 {line_dist['chars_per_line']}\n")
                
                f.write("\n正確な文字別座標詳細:\n")
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
                        f.write(f" 行:{char_detail.get('line', 'N/A')} ブロック:{char_detail.get('block', 'N/A')}")
                    else:
                        f.write("座標なし")
                    f.write(f" (offset: {char_detail['global_offset']}, char_data: {char_detail.get('char_data_offset', 'N/A')})\n")
                
                f.write("\n")
    
    def _generate_accurate_json_report(self, file_path: str):
        """正確な文字座標を反映したJSONレポート生成"""
        report_data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'source_file': self.pdf_path,
                'total_pii_count': len(self.analysis_results),
                'system_version': 'accurate_character_mapping',
                'description': '正確な文字レベル座標解析結果（改行を跨ぐ文字対応）'
            },
            'analysis_results': self.analysis_results
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    def _generate_accurate_csv_report(self, file_path: str):
        """正確な文字座標を反映したCSVレポート生成"""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # ヘッダー
            writer.writerow([
                'PII_Index', 'Entity_Type', 'PII_Text', 'Page', 'Char_Index',
                'Character', 'Global_Offset', 'CharData_Offset', 'X0', 'Y0', 'X1', 'Y1',
                'Width', 'Height', 'Line', 'Block', 'Has_Coordinates', 'System_Version'
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
                        char_detail.get('char_data_offset', ''),
                        char_detail.get('x0', ''),
                        char_detail.get('y0', ''),
                        char_detail.get('x1', ''),
                        char_detail.get('y1', ''),
                        char_detail.get('width', ''),
                        char_detail.get('height', ''),
                        char_detail.get('line', ''),
                        char_detail.get('block', ''),
                        char_detail['has_coordinates'],
                        'accurate'
                    ]
                    writer.writerow(row)

def main():
    """メイン実行関数"""
    test_pdf_path = "./test_japanese_linebreaks.pdf"
    
    if not os.path.exists(test_pdf_path):
        logger.error(f"テストファイルが見つかりません: {test_pdf_path}")
        return
    
    try:
        # 正確な文字座標解析を実行
        generator = AccurateCharacterReportGenerator(test_pdf_path)
        results = generator.generate_accurate_analysis()
        
        logger.info(f"正確な文字座標解析完了: {len(results)}件のPIIを解析")
        
        # 詳細レポート生成
        generator.generate_accurate_reports()
        
        # コンソールサマリー出力
        print("\n" + "="*60)
        print("正確な文字座標解析 - サマリー")
        print("="*60)
        for analysis in results:
            summary = analysis['analysis_summary']
            print(f"PII #{analysis['pii_index']}: '{analysis['text']}' ({analysis['entity_type']})")
            if 'error' not in summary:
                print(f"  文字数: {summary['total_characters']} (座標あり: {summary['characters_with_coordinates']})")
                bbox = summary['bounding_box']
                print(f"  境界: ({bbox['x0']:.2f}, {bbox['y0']:.2f}) - ({bbox['x1']:.2f}, {bbox['y1']:.2f})")
                line_dist = summary['line_distribution']
                print(f"  行分布: {line_dist['total_lines']}行 {line_dist['chars_per_line']}")
            else:
                print(f"  エラー: {summary['error']}")
            print()
        
    except Exception as e:
        logger.error(f"実行エラー: {e}")
        raise

if __name__ == "__main__":
    main()