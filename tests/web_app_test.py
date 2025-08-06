#!/usr/bin/env python3
"""
Web App Test Script for PresidioPDF
MCPサーバーで実行するWebアプリケーションの統合テスト
"""

import os
import time
from playwright.sync_api import sync_playwright


def wait_for_loading_complete(page, timeout=60):
    """ローディングスピナー（ぐるぐる）が消えるまで待機"""
    print("ローディング完了を待機中...")

    # ローディングスピナーの消失を待機
    spinner_selectors = [
        ".spinner-border",
        ".loading",
        "#loadingOverlay",
        ".fa-spinner",
        "[class*='spin']",
        "[class*='loading']",
        ".spinner",
        "[class*='rotate']",
        "[class*='loader']",
    ]

    # より確実な待機ロジック
    max_checks = timeout * 2  # 0.5秒間隔でチェック
    for check in range(max_checks):
        spinner_found = False

        for selector in spinner_selectors:
            try:
                if page.locator(selector).count() > 0:
                    # スピナーが見つかった場合、さらに詳細チェック
                    element = page.locator(selector).first
                    if element.is_visible():
                        spinner_found = True
                        print(
                            f"ローディングスピナー検出: {selector} (チェック {check + 1}/{max_checks})"
                        )
                        break
            except:
                continue

        if not spinner_found:
            print(
                f"ローディングスピナーが検出されませんでした (チェック {check + 1}/{max_checks})"
            )
            # 追加で安全な待機時間を設ける
            time.sleep(3)
            return True

        time.sleep(0.5)

    print(f"警告: {timeout}秒待機してもローディングが完了しませんでした")
    return False


def wait_for_text_extraction_complete(page, timeout=30):
    """テキスト抽出中の文字が消えるまで待機"""
    print("テキスト抽出完了を待機中...")

    extraction_texts = ["抽出中", "処理中", "読み込み中", "解析中", "検出中"]

    max_retries = timeout
    for retry in range(max_retries):
        page_text = page.evaluate("() => document.body.innerText")

        # 抽出中の文字が含まれているかチェック
        has_extraction_text = any(text in page_text for text in extraction_texts)

        if not has_extraction_text:
            print("テキスト抽出が完了しました")
            return True

        print(f"まだ抽出中です... ({retry + 1}/{max_retries})")
        time.sleep(1)

    print("タイムアウト: テキスト抽出が完了しませんでした")
    return False


def take_screenshot_with_retry(page, path, description, max_retries=5):
    """ローディング状態をチェックしてスクリーンショットを撮影"""
    for retry in range(max_retries):
        print(f"{description}を撮影中... (試行 {retry + 1}/{max_retries})")

        # ローディング完了を待機
        loading_complete = wait_for_loading_complete(page, timeout=90)

        if not loading_complete:
            print(
                f"ローディング完了を待機できませんでした (試行 {retry + 1}/{max_retries})"
            )
            time.sleep(5)
            continue

        # 追加の安全待機時間
        time.sleep(2)

        # 撮影前の最終チェック
        spinner_selectors = [
            ".spinner-border",
            ".loading",
            "#loadingOverlay",
            ".fa-spinner",
            "[class*='spin']",
            "[class*='loading']",
            ".spinner",
            "[class*='rotate']",
            "[class*='loader']",
        ]

        spinner_exists = False
        for selector in spinner_selectors:
            try:
                if page.locator(selector).count() > 0:
                    element = page.locator(selector).first
                    if element.is_visible():
                        spinner_exists = True
                        print(f"撮影前にスピナー検出: {selector}")
                        break
            except:
                continue

        if not spinner_exists:
            # スクリーンショット撮影
            page.screenshot(path=path)
            print(f"{description}の撮影が完了しました")
            return True

        print(f"ローディング中のため再撮影します... ({retry + 1}/{max_retries})")
        time.sleep(5)

    print(f"警告: {description}の撮影でローディング状態を完全に回避できませんでした")
    # 最終的にはスクリーンショットを撮影
    page.screenshot(path=path)
    return False


def run_web_app_test():
    """Web アプリケーションの統合テストを実行"""

    # テスト用PDFファイルを選択
    test_pdf = "/workspace/test_pdfs/sony.pdf"

    if not os.path.exists(test_pdf):
        print(f"エラー: テストPDFファイルが見つかりません: {test_pdf}")
        return False

    with sync_playwright() as p:
        # ブラウザを起動（ヘッドレスモード）
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("② localhost:5000にアクセス中...")
            page.goto("http://localhost:5000")
            print(f"ページタイトル: {page.title()}")

            # ページのスクリーンショット
            take_screenshot_with_retry(
                page,
                "/workspace/outputs/01_initial_page.png",
                "初期ページのスクリーンショット",
            )

            print("③ PDFファイルをアップロード中...")
            # ファイルアップロード
            file_input = page.locator('input[type="file"]')
            file_input.set_input_files(test_pdf)
            print(f"アップロード完了: {test_pdf}")

            # ファイルアップロード後のスクリーンショット
            time.sleep(2)
            take_screenshot_with_retry(
                page,
                "/workspace/outputs/02_after_upload.png",
                "ファイルアップロード後のスクリーンショット",
            )

            print("④ 条件設定（必要に応じて）")
            # spaCyモデルの設定確認
            model_select = page.locator('select[name="spacy_model"]')
            if model_select.count() > 0:
                print("spaCyモデル選択が利用可能です")
                # デフォルトのままで進行

            print("⑤ PII検出ボタンをクリック中...")
            # PII検出ボタンをクリック
            detect_button = page.locator('button:has-text("検出開始")')
            if detect_button.count() == 0:
                detect_button = page.locator('button:has-text("個人情報を検出")')
            if detect_button.count() == 0:
                detect_button = page.locator('button:has-text("検出")')
            if detect_button.count() == 0:
                detect_button = page.locator('input[type="submit"]')

            detect_button.click()
            print("PII検出処理を開始しました")

            # 処理完了まで待機（最大60秒）
            print("検出処理の完了を待機中...")
            try:
                # 結果が表示されるまで待機
                page.wait_for_selector(
                    ".results-container, .detection-results, #results", timeout=60000
                )
                print("PII検出処理が完了しました")
            except:
                print("タイムアウト: 60秒以内に処理が完了しませんでした")

            # 処理完了後のスクリーンショット（ローディング完了を待機）
            wait_for_loading_complete(page, timeout=60)
            take_screenshot_with_retry(
                page,
                "/workspace/outputs/03_after_detection.png",
                "検出処理完了後のスクリーンショット",
            )

            print("⑦ 検出結果のテキストデータを取得中...")
            # テキスト抽出完了を待機
            wait_for_text_extraction_complete(page, timeout=30)

            # Ctrl+A で全選択してテキストを取得
            page.keyboard.press("Control+a")
            time.sleep(1)

            # ページの全体テキストを取得
            page_text = page.evaluate("() => document.body.innerText")

            # 選択範囲を解除
            page.click("body")
            time.sleep(0.5)
            print("テキスト選択範囲を解除しました")

            # 結果をファイルに保存
            with open(
                "/workspace/outputs/detection_results_text.txt", "w", encoding="utf-8"
            ) as f:
                f.write(page_text)
            print("検出結果のテキストデータを保存しました")

            print("⑧ PDFを保存してハイライト確認")
            # PDF保存ボタンをクリック
            save_button = page.locator('#saveBtn')
            if save_button.count() > 0 and not save_button.is_disabled():
                print("PDF保存ボタンをクリック中...")
                save_button.click()
                
                # ダウンロード完了まで待機
                print("PDF生成とダウンロードを待機中...")
                time.sleep(10)  # PDFの生成とダウンロードに十分な時間を与える
                
                # ダウンロードされたファイルを確認（ブラウザのデフォルトダウンロードフォルダまたはworkspaceの出力フォルダ）
                download_paths = [
                    "/workspace/downloads",
                    "/workspace/outputs", 
                    "/workspace/web_uploads",
                    "/tmp/downloads"
                ]
                
                downloaded_pdf = None
                for download_path in download_paths:
                    if os.path.exists(download_path):
                        pdf_files = [f for f in os.listdir(download_path) if f.endswith('.pdf')]
                        if pdf_files:
                            # 最新のPDFファイルを取得
                            latest_pdf = max([os.path.join(download_path, f) for f in pdf_files], 
                                           key=os.path.getmtime)
                            downloaded_pdf = latest_pdf
                            print(f"ダウンロードされたPDFを発見: {downloaded_pdf}")
                            break
                
                if not downloaded_pdf:
                    print("警告: ダウンロードされたPDFファイルが見つかりませんでした")
                else:
                    # ダウンロードされたPDFを新しいタブで開いて確認
                    print("⑨ ダウンロードされたPDFをブラウザで開いて確認...")
                    new_tab = browser.new_page()
                    try:
                        # file:// URLでPDFを開く
                        pdf_url = f"file://{downloaded_pdf}"
                        new_tab.goto(pdf_url)
                        
                        # PDFが読み込まれるまで待機
                        time.sleep(5)
                        
                        # ダウンロードされたPDFのスクリーンショットを撮影
                        new_tab.screenshot(
                            path="/workspace/outputs/06_downloaded_pdf_with_highlights.png",
                            full_page=True
                        )
                        print("ダウンロードされたPDFのスクリーンショットを保存しました")
                        
                        # PDFの内容を確認（可能であれば）
                        try:
                            page_text = new_tab.evaluate("() => document.body.innerText")
                            if "個人情報" in page_text or "マスク" in page_text or page_text.strip():
                                print("✅ ダウンロードされたPDFにコンテンツが含まれています")
                            else:
                                print("⚠️  ダウンロードされたPDFのコンテンツを確認できませんでした")
                        except:
                            print("ℹ️  PDFコンテンツの自動読み取りはスキップされました")
                            
                    except Exception as pdf_error:
                        print(f"ダウンロードされたPDFの確認中にエラー: {pdf_error}")
                        # エラー時でもスクリーンショットを撮影
                        try:
                            new_tab.screenshot(path="/workspace/outputs/06_pdf_error_screenshot.png")
                        except:
                            pass
                    finally:
                        new_tab.close()
            else:
                print("PDF保存ボタンが利用できません（無効化されているか見つかりません）")

            print("⑩ PDFビューアのハイライト確認用スクリーンショット撮影中...")
            # PDFビューア部分のスクリーンショット（複数に分けて撮影）

            # 全体スクリーンショット
            wait_for_loading_complete(page)
            page.screenshot(
                path="/workspace/outputs/04_full_page_with_highlights.png",
                full_page=True,
            )
            print("フルページスクリーンショットを保存しました")

            # PDF表示エリアのスクリーンショット
            pdf_viewer = page.locator("#pdf-viewer, .pdf-container, canvas")
            if pdf_viewer.count() > 0:
                wait_for_loading_complete(page)
                pdf_viewer.first.screenshot(
                    path="/workspace/outputs/05_pdf_viewer_highlights.png"
                )
                print("PDFビューアのスクリーンショットを保存しました")

            print("✅ Web App Test が正常に完了しました")
            return True

        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            # エラー時のスクリーンショット
            page.screenshot(path="/workspace/outputs/error_screenshot.png")
            return False

        finally:
            browser.close()


if __name__ == "__main__":
    print("=== PresidioPDF Web App Test ===")
    print("① Flask サーバーが起動済みであることを確認してください")

    # outputsディレクトリが存在しない場合は作成
    os.makedirs("/workspace/outputs", exist_ok=True)

    success = run_web_app_test()

    if success:
        print("\n🎉 テストが正常に完了しました!")
        print("📁 結果ファイル:")
        print("   - /workspace/outputs/detection_results_text.txt (テキストデータ)")
        print("   - /workspace/outputs/*.png (スクリーンショット)")
    else:
        print("\n💥 テストが失敗しました")
        print("📁 エラー情報:")
        print("   - /workspace/outputs/error_screenshot.png")
