#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUIテスト: 同一個人名の重複ハイライト確認
"""

import asyncio
import os
from playwright.async_api import async_playwright

async def test_duplicate_names_highlighting():
    """同一個人名が複数箇所でハイライトされるかテスト"""
    
    async with async_playwright() as p:
        # ブラウザ起動
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            # Webアプリケーションに接続
            print("📋 Webアプリケーションに接続中...")
            await page.goto("http://localhost:5000")
            await page.wait_for_load_state("networkidle")
            
            # PDFアップロード
            print("📄 テストPDFをアップロード中...")
            test_pdf_path = "./test_japanese_linebreaks.pdf"
            if not os.path.exists(test_pdf_path):
                print(f"❌ テストファイルが見つかりません: {test_pdf_path}")
                return
            
            file_input = page.locator('input[type="file"]')
            await file_input.set_input_files(test_pdf_path)
            
            # アップロード処理完了まで待機
            await page.wait_for_timeout(3000)
            
            # 検出開始ボタンをクリック
            print("🔍 個人情報検出を開始...")
            detect_button = page.locator('button:has-text("検出開始"), button:has-text("検出実行"), input[value*="検出"]')
            await detect_button.click()
            
            # 検出処理完了まで待機（最大30秒）
            print("⏳ 検出処理完了まで待機中...")
            await page.wait_for_timeout(15000)
            
            # 結果が表示されるまで待機
            try:
                await page.wait_for_selector('.entity-item, .detection-result, [data-entity-type]', timeout=10000)
                print("✅ 検出結果が表示されました")
            except:
                print("⚠️ 検出結果の表示を待機中...")
                await page.wait_for_timeout(5000)
            
            # スクリーンショット撮影
            screenshot_path = "./test_results_duplicate_names.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"📸 スクリーンショット保存: {screenshot_path}")
            
            # 検出された個人名の数を確認
            person_entities = await page.locator('[data-entity-type="PERSON"], .entity-item:has-text("人名"), .entity-item:has-text("PERSON")').count()
            print(f"🧑 検出された人名エンティティ数: {person_entities}件")
            
            # 田中関連の検出を確認
            tanaka_entities = await page.locator('.entity-item:has-text("田中"), [data-text*="田中"]').count()
            print(f"👨 田中関連の検出数: {tanaka_entities}件")
            
            # 検出結果のテキスト内容を取得
            entity_texts = await page.locator('.entity-item, .detection-result').all_text_contents()
            print("📝 検出されたエンティティ:")
            for i, text in enumerate(entity_texts[:10], 1):  # 最初の10件を表示
                print(f"  {i}. {text.strip()}")
            
            print("🎯 テスト完了: 同一個人名の重複ハイライト確認が完了しました")
            
        except Exception as e:
            print(f"❌ テストエラー: {e}")
            # エラー時もスクリーンショットを撮影
            try:
                await page.screenshot(path="./test_error_duplicate_names.png", full_page=True)
                print("📸 エラー時スクリーンショット保存完了")
            except:
                pass
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_duplicate_names_highlighting())