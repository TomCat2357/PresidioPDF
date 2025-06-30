#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正後の座標精度最終確認テスト
"""

import os
import sys
import logging
from datetime import datetime

# プロジェクトモジュールをインポート
sys.path.append('src')
from presidio_web_core import PresidioPDFWebApp

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_final_coordinate_precision():
    """修正後の座標精度テスト"""
    test_pdf_path = "./test_japanese_linebreaks.pdf"
    
    if not os.path.exists(test_pdf_path):
        logger.error(f"テストファイルが見つかりません: {test_pdf_path}")
        return
    
    try:
        print("="*80)
        print("修正後の座標精度最終確認テスト")
        print("="*80)
        print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"対象ファイル: {test_pdf_path}")
        print()
        
        # PresidioPDFWebAppを初期化
        session_id = "final_test"
        web_app = PresidioPDFWebApp(session_id, use_gpu=False)
        
        # PDFファイルを読み込み
        print("1. PDFファイル読み込み...")
        result = web_app.load_pdf_file(test_pdf_path)
        if not result['success']:
            raise Exception(f"PDF読み込みエラー: {result['message']}")
        print("✅ PDF読み込み成功")
        
        # 個人情報検出を実行
        print("\n2. 個人情報検出実行...")
        detection_result = web_app.run_detection()
        if not detection_result['success']:
            raise Exception(f"検出エラー: {detection_result['message']}")
        
        results = detection_result['results']
        print(f"✅ 検出完了: {len(results)}件")
        
        # 田中関連の結果を抽出
        tanaka_results = [r for r in results if '田中' in r['text']]
        print(f"\n3. 田中関連PII検出結果: {len(tanaka_results)}件")
        
        for i, result in enumerate(tanaka_results, 1):
            print(f"\n【田中関連PII #{i}】")
            print(f"テキスト: '{result['text']}'")
            print(f"エンティティタイプ: {result['entity_type']}")
            print(f"ページ: {result['page']}")
            print(f"オフセット: {result['start']}-{result['end']}")
            
            coords = result['coordinates']
            print(f"座標: ({coords['x0']:.2f}, {coords['y0']:.2f}) - ({coords['x1']:.2f}, {coords['y1']:.2f})")
            
            line_rects = result.get('line_rects', [])
            print(f"複数行矩形: {len(line_rects)}個")
            for j, line_rect in enumerate(line_rects):
                rect = line_rect['rect']
                print(f"  矩形{j+1}: ({rect['x0']:.2f}, {rect['y0']:.2f}) - ({rect['x1']:.2f}, {rect['y1']:.2f})")
        
        # 全体統計
        print("\n" + "="*60)
        print("最終結果サマリー")
        print("="*60)
        
        entity_types = {}
        for result in results:
            etype = result['entity_type']
            entity_types[etype] = entity_types.get(etype, 0) + 1
        
        print(f"検出総数: {len(results)}件")
        print("エンティティタイプ別:")
        for etype, count in sorted(entity_types.items()):
            print(f"  - {etype}: {count}件")
        
        # 座標精度評価
        valid_coords = [r for r in results if r.get('coordinates') and all(
            isinstance(r['coordinates'].get(k), (int, float)) 
            for k in ['x0', 'y0', 'x1', 'y1']
        )]
        
        print(f"\n座標精度:")
        print(f"  - 有効座標: {len(valid_coords)}/{len(results)} ({len(valid_coords)/len(results)*100:.1f}%)")
        
        if tanaka_results:
            tanaka_coords = [(r['coordinates']['x0'], r['coordinates']['y0']) for r in tanaka_results]
            print(f"  - 田中関連座標: {tanaka_coords}")
            
            # 座標が異なることを確認（重複ハイライト問題の解決確認）
            if len(set(tanaka_coords)) == len(tanaka_coords):
                print("  ✅ 田中太郎と田中太朗の座標が正確に区別されています")
            else:
                print("  ❌ 田中太郎と田中太朗の座標に重複があります")
        
        print("\n🎯 修正後の座標精度テスト完了")
        
    except Exception as e:
        logger.error(f"テストエラー: {e}")
        raise

if __name__ == "__main__":
    test_final_coordinate_precision()