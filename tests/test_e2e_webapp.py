
import pytest
from playwright.sync_api import Page, expect
import subprocess
import time
import os

@pytest.fixture(scope="session")
def flask_server():
    """Flaskサーバーをセッションの開始時に起動し、終了時に停止するフィクスチャ"""
    env = os.environ.copy()
    # PYTHONPATHにsrcディレクトリを追加して、webパッケージ内のモジュールをインポートできるようにする
    env["PYTHONPATH"] = os.getcwd() + "/src"
    
    server_process = subprocess.Popen(
        ["python", "-m", "src.web.web_main"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)  # サーバーが起動するのを待つ
    yield
    server_process.terminate()

def test_pdf_upload_and_masking(page: Page, flask_server):
    """
    PDFをアップロードし、PIIを検出し、スクリーンショットを撮り、
    マスキングされたPDFを保存するE2Eテスト
    """
    # 1. Webアプリケーションにアクセス
    page.goto("http://localhost:5000")

    # 2. PDFファイルをアップロード
    file_path = "test_pdfs/sony.pdf"
    page.set_input_files('input[type="file"]', file_path)

    # 3. PIIを検出
    page.get_by_role("button", name="検出開始").click()

    # 検出処理の完了を待つ（ステータスメッセージで判断）
    expect(page.locator("#statusMessage")).to_contain_text("検出完了", timeout=60000)

    # 4. スクリーンショットを撮影
    screenshot_dir = "outputs/reports"
    os.makedirs(screenshot_dir, exist_ok=True)
    page.screenshot(path=f"{screenshot_dir}/screenshot.png")

    # 5. PDFを保存
    with page.expect_download() as download_info:
        page.get_by_role("button", name="PDFを保存").click()
    
    download = download_info.value
    # ダウンロードが完了するのを待つ
    download.save_as(os.path.join(screenshot_dir, download.suggested_filename))

    # ダウンロードされたファイルの存在を確認
    assert os.path.exists(os.path.join(screenshot_dir, download.suggested_filename))
