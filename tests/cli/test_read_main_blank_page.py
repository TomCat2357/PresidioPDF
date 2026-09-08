"""空白ページを含むPDFで、text[]（ページ×ブロックの2D配列）のページインデックスが
実際のPDFページ番号と一致し続けることの退行テスト。

不具合：`_blocks_plain_text`（src/cli/read_main.py）は、抽出ブロックが1つも無い
（完全に空白の）ページを `text[]` から丸ごと省いていた。下流の全処理
（`detect_main._convert_offsets_to_position`、`offset2coordsMap`/`coords2offsetMap`
の生成、GUI の `pipeline_service` 等）は `text[i]` が PDF の 0-based ページ `i`
そのものであることを前提としているため、空白ページより後ろにあるページの検出結果は
すべて実際より手前のページ番号にずれてしまい、誤ったページ・誤った座標で表示・
マスクされていた（例：実ページ30の住所が誤ってページ29に出現する）。

本テストは、空白ページを間に挟んでも `text[]` の要素数と各要素の対応ページが
ずれないこと、およびその後段の `detect` 結果が正しいページ番号を指すことを保証する。
"""

import json

import fitz
from click.testing import CliRunner

from src.cli.detect_main import main as detect_command
from src.cli.read_main import _blocks_plain_text
from src.cli.read_main import main as read_command


def _make_pdf_with_blank_page(path):
    """3ページのPDFを作成する。2ページ目（0-based index 1）は完全に空白。"""
    doc = fitz.open()

    page0 = doc.new_page()
    page0.insert_text((72, 72), "FIRST_PAGE_TEXT")

    # 完全に空白のページ（テキスト挿入なし）。実PDFで発生した不具合の再現条件。
    doc.new_page()

    page2 = doc.new_page()
    page2.insert_text((72, 72), "TARGETADDR12345")

    doc.save(path)
    doc.close()


def test_blocks_plain_text_keeps_one_entry_per_page_including_blank(tmp_path):
    path = str(tmp_path / "blank_page.pdf")
    _make_pdf_with_blank_page(path)

    # フィクスチャが本当に空白ページを生むことを保証（生まないと不具合を再現できない）。
    with fitz.open(path) as doc:
        assert doc.page_count == 3
        raw_blocks_with_lines = sum(
            1 for b in doc[1].get_text("rawdict").get("blocks", []) if "lines" in b
        )
    assert raw_blocks_with_lines == 0, "テスト前提: 2ページ目はブロックを持たない空白ページであること"

    text_2d = _blocks_plain_text(path)

    # 空白ページも欠落させず、PDFページ数と同数のエントリを持つこと。
    assert len(text_2d) == 3
    # 空白ページは空リストとして保持され、後続ページの採番をずらさないこと。
    assert text_2d[1] == []
    # 1ページ目・3ページ目それぞれの内容が正しいページ位置にあること。
    assert any("FIRST_PAGE_TEXT" in block for block in text_2d[0])
    assert any("TARGETADDR12345" in block for block in text_2d[2])


def test_detect_reports_true_page_number_after_blank_page(tmp_path):
    """空白ページの後ろにあるテキストの検出結果が、正しい0-basedページ番号
    （圧縮された配列インデックスではなく実際のPDFページ番号）を指すこと。
    """
    pdf_path = tmp_path / "blank_page.pdf"
    _make_pdf_with_blank_page(str(pdf_path))

    read_json = tmp_path / "read.json"
    detect_json = tmp_path / "detect.json"

    runner = CliRunner()

    read_result = runner.invoke(
        read_command,
        ["--pdf", str(pdf_path), "--out", str(read_json), "--no-map", "--no-highlights"],
    )
    assert read_result.exit_code == 0, read_result.output

    read_data = json.loads(read_json.read_text(encoding="utf-8"))
    text_2d = read_data["text"]
    assert len(text_2d) == 3
    assert text_2d[1] == []

    # ML検出（SudachiPy）の再現性に依存しないよう、カスタム正規表現で検出する。
    detect_result = runner.invoke(
        detect_command,
        [
            "-j",
            str(read_json),
            "--out",
            str(detect_json),
            "--entity",
            "PHONE_NUMBER",  # 標準エンティティは検出させない（--addのみを使う）
            "--add",
            "address:TARGETADDR\\d+",
        ],
    )
    assert detect_result.exit_code == 0, detect_result.output

    detect_data = json.loads(detect_json.read_text(encoding="utf-8"))
    matches = [d for d in detect_data["detect"] if d.get("word") == "TARGETADDR12345"]
    assert len(matches) == 1, detect_data["detect"]

    match = matches[0]
    # 実際のPDFページは0-basedで2番目（3ページ目）。圧縮バグがあると1（空白ページを
    # 詰めた配列上の位置）になり、実在しない/誤ったページを指してしまう。
    assert match["start"]["page_num"] == 2
    assert match["end"]["page_num"] == 2
