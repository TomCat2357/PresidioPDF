#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手動GUIテスト: より詳細な検証
"""

import asyncio
import os
from playwright.async_api import async_playwright

async def test_detailed_gui():
    """詳細なGUIテスト"""
    
    async with async_playwright() as p:
        # ブラウザ起動（非ヘッドレスモード）
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        try:
            # Webアプリケーションに接続
            print("🌐 Webアプリケーションに接続...")
            await page.goto("http://localhost:5000")
            await page.wait_for_load_state("networkidle")
            
            # 初期スクリーンショット
            await page.screenshot(path="./step1_initial.png")
            print("📸 Step 1: 初期画面")
            
            # PDFファイル選択
            print("📁 PDFファイル選択...")
            test_pdf_path = "./test_japanese_linebreaks.pdf"
            if not os.path.exists(test_pdf_path):
                print(f"❌ テストファイルが見つかりません: {test_pdf_path}")
                return
            
            file_input = page.locator('input[type="file"]')
            await file_input.set_input_files(test_pdf_path)
            await page.wait_for_timeout(2000)
            
            # アップロード後スクリーンショット
            await page.screenshot(path="./step2_uploaded.png")
            print("📸 Step 2: PDFアップロード後")
            
            # 検出ボタンを確認
            detect_buttons = await page.locator('button, input[type="submit"], input[type="button"]').all()
            print(f"🔍 検出可能なボタン数: {len(detect_buttons)}")
            
            for i, button in enumerate(detect_buttons):
                text = await button.text_content()
                value = await button.get_attribute('value')
                print(f"  ボタン{i+1}: テキスト='{text}' 値='{value}'")
            
            # 検出開始
            try:
                # 複数の可能性を試行
                detect_selectors = [
                    'button:has-text("検出")',
                    'input[value*="検出"]',
                    'button:has-text("開始")',
                    '#detect-btn',
                    '.detect-button'
                ]
                
                for selector in detect_selectors:
                    try:
                        button = page.locator(selector).first
                        if await button.is_visible():
                            print(f"✅ 検出ボタンが見つかりました: {selector}")
                            await button.click()
                            break
                    except:
                        continue
                else:
                    # フォールバック: 最初のボタンをクリック
                    if detect_buttons:
                        await detect_buttons[0].click()
                        print("🔄 フォールバック: 最初のボタンをクリック")
                
                await page.wait_for_timeout(3000)
                
                # 検出開始後スクリーンショット
                await page.screenshot(path="./step3_detection_started.png")
                print("📸 Step 3: 検出開始後")
                
                # 処理完了まで待機
                print("⏳ 検出処理を待機中...")
                await page.wait_for_timeout(10000)
                
                # 結果確認
                await page.screenshot(path="./step4_results.png")
                print("📸 Step 4: 検出結果")
                
                # DOM内容を確認
                page_content = await page.content()
                with open("./page_content.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
                print("📄 ページ内容をpage_content.htmlに保存")
                
                # エンティティ数の詳細確認
                all_elements = await page.locator('*').all()
                person_count = 0
                tanaka_count = 0
                
                for element in all_elements[:100]:  # 最初の100要素をチェック
                    try:
                        text = await element.text_content()
                        if text and '田中' in text:
                            tanaka_count += 1
                        if text and ('人名' in text or 'PERSON' in text):
                            person_count += 1
                    except:
                        continue
                
                print(f"🔍 詳細検索結果:")
                print(f"  - 人名関連要素: {person_count}個")
                print(f"  - 田中関連要素: {tanaka_count}個")
                
            except Exception as e:
                print(f"❌ 検出処理エラー: {e}")
                await page.screenshot(path="./step_error.png")
            
            # 最終スクリーンショット
            await page.screenshot(path="./step_final.png", full_page=True)
            print("📸 最終スクリーンショット")
            
            # 10秒間表示を維持
            print("👀 10秒間表示を維持...")
            await page.wait_for_timeout(10000)
            
        except Exception as e:
            print(f"❌ テストエラー: {e}")
            await page.screenshot(path="./error_screenshot.png")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_detailed_gui())