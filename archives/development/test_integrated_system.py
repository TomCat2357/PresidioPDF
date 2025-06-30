#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最適化されたPDFTextLocator統合システムのテスト
全体統合後の動作確認
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any
import fitz

# プロジェクトモジュールをインポート
sys.path.append('src')
from presidio_web_core import PresidioPDFWebApp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntegratedSystemTester:
    """統合システムの包括テスト"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.test_results = {}
        
    def run_comprehensive_integration_test(self) -> Dict[str, Any]:
        """包括的統合テストの実行"""
        try:
            logger.info(f"統合システムテスト開始: {self.pdf_path}")
            
            # PresidioPDFWebAppを初期化
            session_id = "integration_test"
            web_app = PresidioPDFWebApp(session_id, use_gpu=False)
            
            # 1. PDFファイル読み込みテスト
            load_result = self._test_pdf_loading(web_app)
            
            # 2. 個人情報検出テスト
            detection_result = self._test_pii_detection(web_app)
            
            # 3. 座標精度テスト
            coordinate_accuracy_result = self._test_coordinate_accuracy(web_app)
            
            # 4. 田中太郎/田中太朗区別テスト
            tanaka_distinction_result = self._test_tanaka_distinction(web_app)
            
            # 5. 改行を跨ぐPIIテスト
            multiline_pii_result = self._test_multiline_pii_support(web_app)
            
            self.test_results = {
                'pdf_loading': load_result,
                'pii_detection': detection_result,
                'coordinate_accuracy': coordinate_accuracy_result,
                'tanaka_distinction': tanaka_distinction_result,
                'multiline_pii_support': multiline_pii_result,
                'overall_assessment': self._assess_overall_integration()
            }
            
            return self.test_results
            
        except Exception as e:
            logger.error(f"統合テストエラー: {e}")
            self.test_results = {'error': str(e)}
            return self.test_results
    
    def _test_pdf_loading(self, web_app: PresidioPDFWebApp) -> Dict[str, Any]:
        """PDFファイル読み込みテスト"""
        try:
            start_time = time.time()
            result = web_app.load_pdf_file(self.pdf_path)
            load_time = time.time() - start_time
            
            return {
                'success': result.get('success', False),
                'load_time': load_time,
                'total_pages': result.get('total_pages', 0),
                'filename': result.get('filename', ''),
                'message': result.get('message', ''),
                'test_passed': result.get('success', False) and load_time < 1.0
            }
            
        except Exception as e:
            logger.error(f"PDF読み込みテストエラー: {e}")
            return {'error': str(e), 'test_passed': False}
    
    def _test_pii_detection(self, web_app: PresidioPDFWebApp) -> Dict[str, Any]:
        """個人情報検出テスト"""
        try:
            start_time = time.time()
            result = web_app.run_detection()
            detection_time = time.time() - start_time
            
            if not result.get('success', False):
                return {
                    'error': result.get('message', 'Unknown error'),
                    'test_passed': False
                }
            
            detected_entities = result.get('results', [])
            
            # 期待されるPIIタイプをチェック
            expected_types = ['PERSON', 'LOCATION', 'DATE_TIME', 'PHONE_NUMBER']
            detected_types = list(set(entity.get('entity_type', '') for entity in detected_entities))
            
            # 田中関連エンティティをチェック
            tanaka_entities = [e for e in detected_entities if '田中' in e.get('text', '')]
            
            return {
                'success': True,
                'detection_time': detection_time,
                'total_entities': len(detected_entities),
                'detected_types': detected_types,
                'expected_types_found': [t for t in expected_types if t in detected_types],
                'tanaka_entities_count': len(tanaka_entities),
                'tanaka_entities': tanaka_entities,
                'test_passed': len(detected_entities) > 0 and len(tanaka_entities) >= 2
            }
            
        except Exception as e:
            logger.error(f"PII検出テストエラー: {e}")
            return {'error': str(e), 'test_passed': False}
    
    def _test_coordinate_accuracy(self, web_app: PresidioPDFWebApp) -> Dict[str, Any]:
        """座標精度テスト"""
        try:
            detected_entities = web_app.detection_results
            
            coordinates_valid = 0
            coordinates_total = 0
            line_rects_count = 0
            
            for entity in detected_entities:
                coordinates_total += 1
                
                # 座標情報をチェック
                coordinates = entity.get('coordinates', {})
                if all(key in coordinates for key in ['x0', 'y0', 'x1', 'y1']):
                    if all(isinstance(coordinates[key], (int, float)) for key in ['x0', 'y0', 'x1', 'y1']):
                        coordinates_valid += 1
                
                # line_rects情報をチェック
                line_rects = entity.get('line_rects', [])
                line_rects_count += len(line_rects)
            
            accuracy_rate = coordinates_valid / coordinates_total if coordinates_total > 0 else 0.0
            
            return {
                'coordinates_valid': coordinates_valid,
                'coordinates_total': coordinates_total,
                'accuracy_rate': accuracy_rate,
                'line_rects_count': line_rects_count,
                'test_passed': accuracy_rate >= 0.9  # 90%以上の精度を期待
            }
            
        except Exception as e:
            logger.error(f"座標精度テストエラー: {e}")
            return {'error': str(e), 'test_passed': False}
    
    def _test_tanaka_distinction(self, web_app: PresidioPDFWebApp) -> Dict[str, Any]:
        """田中太郎/田中太朗区別テスト"""
        try:
            detected_entities = web_app.detection_results
            
            tanaka_taro_entities = [e for e in detected_entities if e.get('text') == '田中太郎']
            tanaka_taro_alt_entities = [e for e in detected_entities if e.get('text') == '田中太朗']
            
            # 座標比較
            coordinate_distinction = False
            if tanaka_taro_entities and tanaka_taro_alt_entities:
                taro_coords = tanaka_taro_entities[0].get('coordinates', {})
                taro_alt_coords = tanaka_taro_alt_entities[0].get('coordinates', {})
                
                # Y座標の差をチェック（異なる位置にあることを確認）
                if 'y0' in taro_coords and 'y0' in taro_alt_coords:
                    y_diff = abs(taro_coords['y0'] - taro_alt_coords['y0'])
                    coordinate_distinction = y_diff > 50  # 50ピクセル以上の差
            
            return {
                'tanaka_taro_count': len(tanaka_taro_entities),
                'tanaka_taro_alt_count': len(tanaka_taro_alt_entities),
                'both_detected': len(tanaka_taro_entities) > 0 and len(tanaka_taro_alt_entities) > 0,
                'coordinate_distinction': coordinate_distinction,
                'tanaka_taro_coords': tanaka_taro_entities[0].get('coordinates', {}) if tanaka_taro_entities else {},
                'tanaka_taro_alt_coords': tanaka_taro_alt_entities[0].get('coordinates', {}) if tanaka_taro_alt_entities else {},
                'test_passed': len(tanaka_taro_entities) > 0 and len(tanaka_taro_alt_entities) > 0 and coordinate_distinction
            }
            
        except Exception as e:
            logger.error(f"田中区別テストエラー: {e}")
            return {'error': str(e), 'test_passed': False}
    
    def _test_multiline_pii_support(self, web_app: PresidioPDFWebApp) -> Dict[str, Any]:
        """改行を跨ぐPIIサポートテスト"""
        try:
            detected_entities = web_app.detection_results
            
            multiline_entities = []
            for entity in detected_entities:
                line_rects = entity.get('line_rects', [])
                if len(line_rects) > 1:
                    multiline_entities.append({
                        'text': entity.get('text', ''),
                        'entity_type': entity.get('entity_type', ''),
                        'line_rects_count': len(line_rects)
                    })
            
            return {
                'multiline_entities_count': len(multiline_entities),
                'multiline_entities': multiline_entities,
                'test_passed': len(multiline_entities) > 0  # 改行を跨ぐPIIが検出されることを期待
            }
            
        except Exception as e:
            logger.error(f"改行跨ぎPIIテストエラー: {e}")
            return {'error': str(e), 'test_passed': False}
    
    def _assess_overall_integration(self) -> Dict[str, Any]:
        """総合評価"""
        if 'error' in self.test_results:
            return {'rating': 'failed', 'reason': 'test_execution_error'}
        
        test_categories = ['pdf_loading', 'pii_detection', 'coordinate_accuracy', 'tanaka_distinction', 'multiline_pii_support']
        passed_tests = 0
        
        for category in test_categories:
            if category in self.test_results:
                if self.test_results[category].get('test_passed', False):
                    passed_tests += 1
        
        success_rate = passed_tests / len(test_categories)
        
        if success_rate >= 0.9:
            return {'rating': 'excellent', 'success_rate': success_rate, 'recommendation': 'production_ready'}
        elif success_rate >= 0.7:
            return {'rating': 'good', 'success_rate': success_rate, 'recommendation': 'suitable_for_use'}
        elif success_rate >= 0.5:
            return {'rating': 'fair', 'success_rate': success_rate, 'recommendation': 'needs_improvement'}
        else:
            return {'rating': 'poor', 'success_rate': success_rate, 'recommendation': 'requires_fixes'}
    
    def generate_integration_test_report(self) -> str:
        """統合テストレポート生成"""
        if not self.test_results:
            return "テスト結果がありません"
        
        lines = []
        lines.append("=" * 80)
        lines.append("最適化PDFTextLocator統合システムテストレポート")
        lines.append("=" * 80)
        lines.append(f"生成時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"対象ファイル: {self.pdf_path}")
        lines.append("")
        
        # 各テスト結果
        test_categories = {
            'pdf_loading': 'PDFファイル読み込み',
            'pii_detection': '個人情報検出',
            'coordinate_accuracy': '座標精度',
            'tanaka_distinction': '田中太郎/太朗区別',
            'multiline_pii_support': '改行跨ぎPII対応'
        }
        
        for category, title in test_categories.items():
            result = self.test_results.get(category, {})
            if 'error' not in result:
                status = "✅" if result.get('test_passed', False) else "❌"
                lines.append(f"{status} 【{title}テスト】")
                lines.append("-" * 40)
                
                if category == 'pdf_loading':
                    lines.append(f"読み込み時間: {result.get('load_time', 0):.4f}秒")
                    lines.append(f"総ページ数: {result.get('total_pages', 0)}")
                
                elif category == 'pii_detection':
                    lines.append(f"検出時間: {result.get('detection_time', 0):.4f}秒")
                    lines.append(f"検出エンティティ数: {result.get('total_entities', 0)}")
                    lines.append(f"検出タイプ: {result.get('detected_types', [])}")
                    lines.append(f"田中関連エンティティ: {result.get('tanaka_entities_count', 0)}件")
                
                elif category == 'coordinate_accuracy':
                    lines.append(f"座標精度: {result.get('accuracy_rate', 0):.1%}")
                    lines.append(f"有効座標: {result.get('coordinates_valid', 0)}/{result.get('coordinates_total', 0)}")
                    lines.append(f"line_rects数: {result.get('line_rects_count', 0)}")
                
                elif category == 'tanaka_distinction':
                    lines.append(f"田中太郎検出: {result.get('tanaka_taro_count', 0)}件")
                    lines.append(f"田中太朗検出: {result.get('tanaka_taro_alt_count', 0)}件")
                    lines.append(f"座標区別: {'✅' if result.get('coordinate_distinction', False) else '❌'}")
                
                elif category == 'multiline_pii_support':
                    lines.append(f"改行跨ぎPII: {result.get('multiline_entities_count', 0)}件")
                    for entity in result.get('multiline_entities', []):
                        lines.append(f"  - {entity['text']} ({entity['entity_type']}): {entity['line_rects_count']}行")
            
            else:
                lines.append(f"❌ 【{title}テスト】")
                lines.append(f"エラー: {result['error']}")
            
            lines.append("")
        
        # 総合評価
        overall = self.test_results.get('overall_assessment', {})
        lines.append("【総合評価】")
        lines.append("=" * 40)
        lines.append(f"評価: {overall.get('rating', 'unknown')}")
        lines.append(f"成功率: {overall.get('success_rate', 0):.1%}")
        lines.append(f"推奨: {overall.get('recommendation', 'unknown')}")
        
        return "\n".join(lines)

def main():
    """メイン実行関数"""
    test_pdf_path = "./test_japanese_linebreaks.pdf"
    
    if not os.path.exists(test_pdf_path):
        logger.error(f"テストファイルが見つかりません: {test_pdf_path}")
        return
    
    try:
        # 統合テスト実行
        tester = IntegratedSystemTester(test_pdf_path)
        results = tester.run_comprehensive_integration_test()
        
        # レポート生成
        report = tester.generate_integration_test_report()
        
        # ファイル保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"integrated_system_test_report_{timestamp}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # 詳細データ保存
        json_path = f"integrated_system_test_data_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"統合システムテスト完了:")
        logger.info(f"  - レポート: {report_path}")
        logger.info(f"  - 詳細データ: {json_path}")
        
        # コンソール出力
        print("\n" + report)
        
    except Exception as e:
        logger.error(f"統合テスト実行エラー: {e}")
        raise

if __name__ == "__main__":
    main()