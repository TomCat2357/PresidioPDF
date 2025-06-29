
import subprocess
import time
from pathlib import Path
import pytest
import requests
from playwright.sync_api import sync_playwright, expect

# サーバーのベースURL
BASE_URL = "http://localhost:5000"
# テスト用のPDFファイル
TEST_PDF = Path("test_pdfs/a1.pdf")

@pytest.fixture(scope="session")
def live_server():
    """uv runでWebアプリケーションを起動するpytestフィクスチャ"""
    # uv runコマンドでサーバーをバックグラウンドで起動
    # uvが見つからない場合は、python -m uvicornを試す
    try:
        process = subprocess.Popen(
            ["uv", "run", "python", "src/web_main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        process = subprocess.Popen(
            ["python", "src/web_main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    # サーバーが起動するのを待つ
    for _ in range(30):
        try:
            response = requests.get(BASE_URL, timeout=1)
            if response.status_code == 200:
                print(f"サーバーが {BASE_URL} で起動しました。")
                break
        except requests.exceptions.RequestException:
            time.sleep(1)
    else:
        # タイムアウトした場合、プロセスを終了させてエラーを発生させる
        process.terminate()
        process.wait()
        pytest.fail(f"サーバーが起動しませんでした。ログ: {process.stderr.read().decode()}")

    # テスト実行
    yield BASE_URL

    # テスト終了後にサーバーを停止
    print("サーバーを停止します。")
    process.terminate()
    process.wait()

def test_pdf_anonymization_e2e(live_server):
    """PDFの匿名化処理のE2Eテスト"""
    if not TEST_PDF.exists():
        pytest.skip(f"テストPDFファイルが見つかりません: {TEST_PDF}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # ヘッドレスモードで実行
        page = browser.new_page()

        console_messages = []
        page.on("console", lambda msg: console_messages.append(msg.text))

        try:
            # 1. localhost:5000を開く
            page.goto(live_server)
            print("ページにアクセスしました。")

            # 2. test_pdfs/a1.pdfをアップロードする
            print(f"PDFファイル {TEST_PDF.absolute()} をアップロードします。")
            page.locator('input[type="file"]').set_input_files(str(TEST_PDF.absolute()))

            # 3. ちょっと待つ
            page.wait_for_timeout(2000)  # 2秒待機
            print("PDFをアップロードしました。")

            # 4. 設定はスキップしてデフォルトモデルで実行
            print("設定をスキップして、デフォルトモデルで検出を実行します。")

            # 5. 検出ボタンを押す
            start_button = page.locator('button:has-text("検出開始")')
            expect(start_button).to_be_enabled()
            # APIのレスポンスをキャプチャ（タイムアウトを3分に延長）
            with page.expect_response("**/api/detect", timeout=180000) as response_info:
                start_button.click()
            
            response = response_info.value
            response_body = response.json()
            print(f"検出APIのレスポンス: {response_body}")

            # 6. ちょっと待つ（処理完了を待機）
            # プレースホルダーでない、実際の検出結果が表示されるまで待つ
            result_list_items = page.locator('#entityList .list-group-item:not(:has-text("検出結果がここに表示されます"))')
            expect(result_list_items.first).to_be_visible(timeout=180000)
            print("実際の検出結果が表示されました。")

            # ハイライトが描画されるのを待つ
            highlight_rects = page.locator(".highlight-rect")
            expect(highlight_rects.first).to_be_visible(timeout=10000)
            print(f"{highlight_rects.count()}個のハイライトが表示されました。")

            # 7. 写真をとる
            page.wait_for_timeout(3000) # 描画が安定するまで待機
            screenshot_path = "test-results/screenshot_with_highlights.png"
            Path("test-results").mkdir(exist_ok=True)
            page.screenshot(path=screenshot_path)
            print(f"ハイライト付きのスクリーンショットを {screenshot_path} に保存しました。")

            # 8. 解析する
            page_content = page.content()
            assert "検出結果" in page_content
            save_button = page.locator('button:has-text("PDFを保存")')
            expect(save_button).to_be_visible()
            assert result_list_items.count() > 0, "検出結果がリストに表示されていません。"
            assert highlight_rects.count() > 0, "ハイライトがPDF上に描画されていません。"
            print(f"結果の解析が完了しました。検出数: {result_list_items.count()}")

        except Exception as e:
            # エラー発生時にデバッグ情報を保存
            debug_dir = Path("test-results/debug")
            debug_dir.mkdir(exist_ok=True, parents=True)
            page.screenshot(path=str(debug_dir / "error_screenshot.png"))
            with open(debug_dir / "error_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            with open(debug_dir / "console_log.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(console_messages))
            
            print(f"テストが失敗しました。デバッグ情報は {debug_dir} に保存されました。")
            raise e

        finally:
            browser.close()
