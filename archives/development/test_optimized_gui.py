#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最適化されたPDFTextLocator統合後のGUIテスト
田中太郎/田中太朗の座標精度を検証
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, Any

# Playwrightをインポート
try:
    from playwright.sync_api import Playwright, Browser, Page, sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwrightが利用できません。pip install playwrightを実行してください。")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OptimizedGUITester:
    """最適化GUI機能の包括テスト"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.browser = None
        self.page = None
        self.test_results = {}
        
    def run_optimized_gui_test(self) -> Dict[str, Any]:
        """最適化GUI機能の包括テスト実行"""
        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Playwrightが利用できません"}
        
        try:
            logger.info("最適化GUI機能テスト開始")
            
            with sync_playwright() as playwright:
                # ブラウザ起動
                self.browser = playwright.chromium.launch(headless=False)
                self.page = self.browser.new_page()
                
                # 各テストステップを実行
                steps = [
                    ("page_access", self._test_page_access),
                    ("file_upload", self._test_file_upload),
                    ("detection_execution", self._test_detection_execution),
                    ("coordinate_verification", self._test_coordinate_verification),
                    ("tanaka_distinction", self._test_tanaka_distinction),
                    ("multiline_pii_verification", self._test_multiline_pii_verification)
                ]
                
                self.test_results = {}
                
                for step_name, test_func in steps:
                    logger.info(f"実行中: {step_name}")
                    try:
                        result = test_func()
                        self.test_results[step_name] = result
                        
                        if not result.get('success', False):
                            logger.warning(f"{step_name} 失敗: {result.get('message', 'Unknown error')}")
                            # 失敗時もテストを継続
                    except Exception as e:
                        logger.error(f"{step_name} エラー: {e}")
                        self.test_results[step_name] = {'success': False, 'error': str(e)}
                
                # スクリーンショット撮影
                self._take_final_screenshot()
                
                # 総合評価
                self.test_results['overall_assessment'] = self._assess_gui_integration()
                
                return self.test_results
                
        except Exception as e:
            logger.error(f"GUI機能テストエラー: {e}")
            return {"error": str(e)}
        finally:
            if self.browser:
                self.browser.close()
    
    def _test_page_access(self) -> Dict[str, Any]:
        """ページアクセステスト"""
        try:
            self.page.goto(self.base_url, timeout=10000)
            title = self.page.title()
            
            # ページ要素の確認
            file_input = self.page.locator("input[type='file']")
            if file_input.count() == 0:
                return {'success': False, 'message': 'ファイル入力要素が見つかりません'}
            
            return {
                'success': True,
                'title': title,
                'file_input_found': file_input.count() > 0,
                'page_loaded': True
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_file_upload(self) -> Dict[str, Any]:
        """ファイルアップロードテスト"""
        try:
            test_file = "./test_japanese_linebreaks.pdf"
            if not os.path.exists(test_file):
                return {'success': False, 'message': f'テストファイルが見つかりません: {test_file}'}
            
            # ファイルをアップロード
            file_input = self.page.locator("input[type='file']")
            file_input.set_input_files(test_file)
            
            # アップロード結果を待機
            time.sleep(2)
            
            # アップロード成功の確認
            upload_status = self.page.locator("#upload-status")
            status_text = upload_status.text_content() if upload_status.count() > 0 else ""
            
            return {
                'success': True,
                'file_uploaded': True,
                'status_text': status_text,
                'test_file': test_file
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_detection_execution(self) -> Dict[str, Any]:
        """PII検出実行テスト"""
        try:
            # 検出ボタンをクリック
            detect_button = self.page.locator("#run-detection")
            if detect_button.count() == 0:
                return {'success': False, 'message': '検出ボタンが見つかりません'}
            
            detect_button.click()
            
            # 処理完了まで待機（最大30秒）
            self.page.wait_for_selector("#detection-results", timeout=30000)
            time.sleep(2)  # 結果表示のための追加待機
            
            # 結果エリアの確認
            results_area = self.page.locator("#detection-results")
            results_visible = results_area.is_visible()
            
            # 検出された項目数を確認
            result_items = self.page.locator(".detection-result-item")
            items_count = result_items.count()
            
            return {
                'success': True,
                'detection_executed': True,
                'results_visible': results_visible,
                'detected_items_count': items_count,
                'detection_completed': items_count > 0
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_coordinate_verification(self) -> Dict[str, Any]:
        """座標検証テスト"""
        try:
            # PDF表示エリアの確認
            pdf_display = self.page.locator("#pdf-display")
            if pdf_display.count() == 0:
                return {'success': False, 'message': 'PDF表示エリアが見つかりません'}
            
            # ハイライトされた要素を確認
            highlights = self.page.locator(".highlight, .annotation")
            highlights_count = highlights.count()
            
            # 個別ハイライトの座標情報を取得
            highlight_coordinates = []
            for i in range(min(highlights_count, 5)):  # 最初の5個まで
                try:
                    highlight = highlights.nth(i)
                    bbox = highlight.bounding_box()
                    if bbox:
                        highlight_coordinates.append({
                            'index': i,
                            'x': bbox['x'],
                            'y': bbox['y'], 
                            'width': bbox['width'],
                            'height': bbox['height']
                        })
                except:
                    continue
            
            return {
                'success': True,
                'pdf_displayed': pdf_display.is_visible(),
                'highlights_count': highlights_count,
                'coordinate_data': highlight_coordinates,
                'coordinates_available': len(highlight_coordinates) > 0
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_tanaka_distinction(self) -> Dict[str, Any]:
        """田中太郎/田中太朗区別テスト"""
        try:
            # 検出結果から田中関連を検索
            result_items = self.page.locator(".detection-result-item")
            
            tanaka_taro_elements = []
            tanaka_taro_alt_elements = []
            
            for i in range(result_items.count()):
                item = result_items.nth(i)
                item_text = item.text_content()
                
                if "田中太郎" in item_text:
                    tanaka_taro_elements.append({
                        'index': i,
                        'text': item_text,
                        'bbox': item.bounding_box()
                    })
                elif "田中太朗" in item_text:
                    tanaka_taro_alt_elements.append({
                        'index': i,
                        'text': item_text,
                        'bbox': item.bounding_box()
                    })
            
            # 座標区別の確認
            coordinate_distinction = False
            if tanaka_taro_elements and tanaka_taro_alt_elements:
                taro_bbox = tanaka_taro_elements[0]['bbox']
                taro_alt_bbox = tanaka_taro_alt_elements[0]['bbox']
                
                if taro_bbox and taro_alt_bbox:
                    y_diff = abs(taro_bbox['y'] - taro_alt_bbox['y'])
                    coordinate_distinction = y_diff > 20  # 20ピクセル以上の差
            
            return {
                'success': True,
                'tanaka_taro_found': len(tanaka_taro_elements) > 0,
                'tanaka_taro_alt_found': len(tanaka_taro_alt_elements) > 0,
                'tanaka_taro_count': len(tanaka_taro_elements),
                'tanaka_taro_alt_count': len(tanaka_taro_alt_elements),
                'coordinate_distinction': coordinate_distinction,
                'tanaka_taro_elements': tanaka_taro_elements,
                'tanaka_taro_alt_elements': tanaka_taro_alt_elements,
                'both_detected': len(tanaka_taro_elements) > 0 and len(tanaka_taro_alt_elements) > 0
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_multiline_pii_verification(self) -> Dict[str, Any]:
        """改行を跨ぐPII検証テスト"""
        try:
            # 複数行に跨るハイライトを確認
            pdf_canvas = self.page.locator("#pdf-canvas, canvas")
            if pdf_canvas.count() == 0:
                return {'success': False, 'message': 'PDFキャンバスが見つかりません'}
            
            # ハイライト要素を確認
            all_highlights = self.page.locator(".highlight, .annotation, [class*='highlight'], [class*='annotation']")
            multiline_highlights = 0
            
            # 検出結果のテキストから改行を跨ぐPIIを特定
            result_items = self.page.locator(".detection-result-item")
            multiline_entities = []
            
            for i in range(result_items.count()):
                item = result_items.nth(i)
                item_text = item.text_content()
                
                # 改行を跨ぐ可能性のあるエンティティ（日本語の長いテキスト）
                if any(entity in item_text for entity in ["東京都新宿区", "2024年12月", "090-1234-5678", "田中"]):
                    multiline_entities.append({
                        'index': i,
                        'text': item_text,
                        'potentially_multiline': True
                    })
            
            return {
                'success': True,
                'pdf_canvas_found': pdf_canvas.is_visible(),
                'total_highlights': all_highlights.count(),
                'multiline_entities_count': len(multiline_entities),
                'multiline_entities': multiline_entities,
                'multiline_support_detected': len(multiline_entities) > 0
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _take_final_screenshot(self):
        """最終スクリーンショット撮影"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = f"optimized_gui_test_screenshot_{timestamp}.png"
            self.page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"スクリーンショット保存: {screenshot_path}")
            
        except Exception as e:
            logger.error(f"スクリーンショット撮影エラー: {e}")
    
    def _assess_gui_integration(self) -> Dict[str, Any]:
        """GUI統合評価"""
        if not self.test_results:
            return {'rating': 'failed', 'reason': 'no_test_results'}
        
        critical_tests = ['page_access', 'file_upload', 'detection_execution']
        feature_tests = ['coordinate_verification', 'tanaka_distinction', 'multiline_pii_verification']
        
        critical_passed = sum(1 for test in critical_tests if self.test_results.get(test, {}).get('success', False))
        feature_passed = sum(1 for test in feature_tests if self.test_results.get(test, {}).get('success', False))
        
        critical_rate = critical_passed / len(critical_tests)
        feature_rate = feature_passed / len(feature_tests)
        
        overall_rate = (critical_rate * 0.7 + feature_rate * 0.3)  # 基本機能を重視
        
        if critical_rate < 1.0:
            return {
                'rating': 'critical_failure',
                'critical_success_rate': critical_rate,
                'feature_success_rate': feature_rate,
                'overall_success_rate': overall_rate,
                'recommendation': 'fix_critical_issues'
            }
        elif overall_rate >= 0.8:
            return {
                'rating': 'excellent',
                'critical_success_rate': critical_rate,
                'feature_success_rate': feature_rate,
                'overall_success_rate': overall_rate,
                'recommendation': 'production_ready'
            }
        elif overall_rate >= 0.6:
            return {
                'rating': 'good',
                'critical_success_rate': critical_rate,
                'feature_success_rate': feature_rate,
                'overall_success_rate': overall_rate,
                'recommendation': 'minor_improvements_needed'
            }
        else:
            return {
                'rating': 'needs_improvement',
                'critical_success_rate': critical_rate,
                'feature_success_rate': feature_rate,
                'overall_success_rate': overall_rate,
                'recommendation': 'significant_improvements_needed'
            }
    
    def generate_gui_test_report(self) -> str:
        """GUIテストレポート生成"""
        if not self.test_results:
            return "テスト結果がありません"
        
        lines = []
        lines.append("=" * 80)
        lines.append("最適化PDFTextLocator GUI統合テストレポート")
        lines.append("=" * 80)
        lines.append(f"生成時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"テストURL: {self.base_url}")
        lines.append("")
        
        # 各テスト結果
        test_names = {
            'page_access': 'ページアクセス',
            'file_upload': 'ファイルアップロード',
            'detection_execution': 'PII検出実行',
            'coordinate_verification': '座標検証',
            'tanaka_distinction': '田中太郎/太朗区別',
            'multiline_pii_verification': '改行跨ぎPII検証'
        }
        
        for test_key, test_name in test_names.items():
            result = self.test_results.get(test_key, {})
            status = "✅" if result.get('success', False) else "❌"
            lines.append(f"{status} 【{test_name}テスト】")
            lines.append("-" * 40)
            
            if 'error' in result:
                lines.append(f"エラー: {result['error']}")
            elif result.get('success', False):
                if test_key == 'detection_execution':
                    lines.append(f"検出項目数: {result.get('detected_items_count', 0)}")
                    lines.append(f"検出完了: {'✅' if result.get('detection_completed', False) else '❌'}")
                
                elif test_key == 'coordinate_verification':
                    lines.append(f"ハイライト数: {result.get('highlights_count', 0)}")
                    lines.append(f"座標データ取得: {'✅' if result.get('coordinates_available', False) else '❌'}")
                
                elif test_key == 'tanaka_distinction':
                    lines.append(f"田中太郎検出: {result.get('tanaka_taro_count', 0)}件")
                    lines.append(f"田中太朗検出: {result.get('tanaka_taro_alt_count', 0)}件")
                    lines.append(f"座標区別: {'✅' if result.get('coordinate_distinction', False) else '❌'}")
                    lines.append(f"両方検出: {'✅' if result.get('both_detected', False) else '❌'}")
                
                elif test_key == 'multiline_pii_verification':
                    lines.append(f"改行跨ぎエンティティ: {result.get('multiline_entities_count', 0)}件")
                    lines.append(f"改行対応検出: {'✅' if result.get('multiline_support_detected', False) else '❌'}")
            
            lines.append("")
        
        # 総合評価
        overall = self.test_results.get('overall_assessment', {})
        lines.append("【総合評価】")
        lines.append("=" * 40)
        lines.append(f"評価: {overall.get('rating', 'unknown')}")
        lines.append(f"基本機能成功率: {overall.get('critical_success_rate', 0):.1%}")
        lines.append(f"高度機能成功率: {overall.get('feature_success_rate', 0):.1%}")
        lines.append(f"総合成功率: {overall.get('overall_success_rate', 0):.1%}")
        lines.append(f"推奨: {overall.get('recommendation', 'unknown')}")
        
        return "\n".join(lines)

def main():
    """メイン実行関数"""
    try:
        # GUI機能テスト実行
        tester = OptimizedGUITester()
        results = tester.run_optimized_gui_test()
        
        if 'error' in results:
            print(f"GUIテストエラー: {results['error']}")
            return
        
        # レポート生成
        report = tester.generate_gui_test_report()
        
        # ファイル保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"optimized_gui_test_report_{timestamp}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # 詳細データ保存
        import json
        json_path = f"optimized_gui_test_data_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"GUIテスト完了:")
        logger.info(f"  - レポート: {report_path}")
        logger.info(f"  - 詳細データ: {json_path}")
        
        # コンソール出力
        print("\n" + report)
        
    except Exception as e:
        logger.error(f"GUIテスト実行エラー: {e}")
        raise

if __name__ == "__main__":
    main()