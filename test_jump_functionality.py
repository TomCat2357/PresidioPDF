#!/usr/bin/env python3
"""
PDFリスト⇔PDFビューア間のジャンプ機能テスト
sony.pdfを使用して相互ジャンプが正常に動作するかを検証
"""
import asyncio
import time
from playwright.async_api import async_playwright
import os

async def test_jump_functionality():
    """リスト⇔PDFビューアのジャンプ機能をテスト"""
    
    async with async_playwright() as p:
        # ブラウザを起動（headlessモード）
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print("=== PDFジャンプ機能テスト開始 ===")
            
            # 1. Webアプリにアクセス
            print("1. Webアプリにアクセス...")
            await page.goto("http://localhost:5000", timeout=30000)
            await page.wait_for_load_state('networkidle')
            
            # 初期状態のスクリーンショット
            await page.screenshot(path="/workspace/outputs/jump_test_01_initial.png", full_page=True)
            
            # 2. テスト用PDFをアップロード
            print("2. テスト用PDFをアップロード...")
            
            # より簡単なテスト用PDFを使用
            test_pdf_candidates = [
                "/workspace/test_pdfs/a1.pdf",
                "/workspace/test_pdfs/harumichi.pdf", 
                "/workspace/test_pdfs/dummy_data.pdf",
                "/workspace/test_pdfs/sony.pdf"
            ]
            
            sony_pdf_path = None
            for candidate in test_pdf_candidates:
                if os.path.exists(candidate):
                    sony_pdf_path = candidate
                    print(f"テスト用PDFとして {os.path.basename(candidate)} を使用します")
                    break
            
            if not sony_pdf_path:
                print("ERROR: 利用可能なPDFファイルが見つかりません")
                return
            
            # ファイル選択フィールドにファイルをセット
            file_input = page.locator('#pdfFileInput')
            await file_input.set_input_files(sony_pdf_path)
            
            # アップロード完了まで待機
            await page.wait_for_timeout(3000)
            await page.screenshot(path="/workspace/outputs/jump_test_02_uploaded.png", full_page=True)
            
            # 3. PII検出を実行
            print("3. PII検出を実行...")
            detect_button = page.locator('#detectBtn')
            await detect_button.click()
            
            # 検出処理完了まで待機（最大60秒）
            try:
                await page.wait_for_selector('#entityList .list-group-item:not(.text-muted)', timeout=60000)
                print("PII検出完了")
            except:
                print("WARNING: PII検出完了の検出がタイムアウトしました")
            
            await page.wait_for_timeout(2000)
            await page.screenshot(path="/workspace/outputs/jump_test_03_detection_done.png", full_page=True)
            
            # 4. エンティティリストの要素数を確認
            entity_items = page.locator('#entityList .list-group-item:not(.text-muted)')
            entity_count = await entity_items.count()
            print(f"検出されたエンティティ数: {entity_count}")
            
            if entity_count == 0:
                print("ERROR: エンティティが検出されませんでした")
                return
            
            # 5. 最初のエンティティをクリックしてPDFにジャンプ
            print("5. リスト→PDFジャンプをテスト...")
            
            # 最初のエンティティの情報を取得
            first_entity = entity_items.first
            first_entity_text = await first_entity.locator('p').text_content()
            print(f"最初のエンティティ: {first_entity_text}")
            
            # エンティティをクリック（clickable部分をクリック）
            await first_entity.locator('.flex-grow-1').click()
            await page.wait_for_timeout(1000)
            
            # ジャンプ後のスクリーンショット
            await page.screenshot(path="/workspace/outputs/jump_test_04_list_to_pdf_jump.png", full_page=True)
            
            # 6. PDFでハイライトが選択されているかチェック
            selected_highlights = page.locator('.highlight-rect.selected')
            selected_count = await selected_highlights.count()
            print(f"選択されたハイライト数: {selected_count}")
            
            # 7. 別のエンティティをテスト（2番目があれば）
            if entity_count > 1:
                print("7. 2番目のエンティティでテスト...")
                second_entity = entity_items.nth(1)
                second_entity_text = await second_entity.locator('p').text_content()
                print(f"2番目のエンティティ: {second_entity_text}")
                
                await second_entity.locator('.flex-grow-1').click()
                await page.wait_for_timeout(1000)
                await page.screenshot(path="/workspace/outputs/jump_test_05_second_entity_jump.png", full_page=True)
            
            # 8. PDFハイライト→リストジャンプをテスト
            print("8. PDF→リストジャンプをテスト...")
            
            # ハイライト要素を探してクリック
            highlight_elements = page.locator('.highlight-rect')
            highlight_count = await highlight_elements.count()
            print(f"PDFのハイライト数: {highlight_count}")
            
            if highlight_count > 0:
                # 最初のハイライトをクリック
                first_highlight = highlight_elements.first
                await first_highlight.click()
                await page.wait_for_timeout(1000)
                
                # PDF→リストジャンプ後のスクリーンショット
                await page.screenshot(path="/workspace/outputs/jump_test_06_pdf_to_list_jump.png", full_page=True)
                
                # リストで選択されているアイテムをチェック
                active_list_items = page.locator('#entityList .list-group-item.active')
                active_count = await active_list_items.count()
                print(f"アクティブなリストアイテム数: {active_count}")
                
                if active_count > 0:
                    active_text = await active_list_items.first.locator('p').text_content()
                    print(f"アクティブなエンティティ: {active_text}")
            
            # 9. 最終状態のスクリーンショット
            await page.screenshot(path="/workspace/outputs/jump_test_07_final_state.png", full_page=True)
            
            # 10. テスト結果の詳細情報を収集
            print("10. テスト結果の詳細情報を収集...")
            
            # JavaScript実行でアプリの状態を取得
            app_state = await page.evaluate("""
                () => {
                    if (window.app) {
                        return {
                            selectedEntityIndex: window.app.selectedEntityIndex,
                            detectionResultsCount: window.app.detectionResults.length,
                            currentPage: window.app.currentPage,
                            totalPages: window.app.totalPages
                        };
                    }
                    return null;
                }
            """)
            print(f"アプリ状態: {app_state}")
            
            # 結果をテキストファイルに保存
            test_results = f"""
=== PDFジャンプ機能テスト結果 ===
実行時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}

検出されたエンティティ数: {entity_count}
PDFのハイライト数: {highlight_count}
選択されたハイライト数: {selected_count}
アクティブなリストアイテム数: {active_count if 'active_count' in locals() else 'N/A'}

アプリケーション状態:
{app_state}

テスト完了: 相互ジャンプ機能のスクリーンショットを outputs/ に保存しました
"""
            
            with open("/workspace/outputs/jump_test_results.txt", "w", encoding="utf-8") as f:
                f.write(test_results)
            
            print("=== テスト完了 ===")
            print("スクリーンショットは /workspace/outputs/ に保存されました")
            
        except Exception as e:
            print(f"テスト中にエラーが発生しました: {e}")
            await page.screenshot(path="/workspace/outputs/jump_test_error.png", full_page=True)
            
        finally:
            # ブラウザを閉じる
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_jump_functionality())