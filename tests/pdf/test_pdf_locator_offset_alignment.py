"""PDFTextLocator のグローバルオフセット空間が正準採番（PDFBlockTextMapper）と
一致することの退行テスト。

不具合：locator は空白のみブロック（表の空セル・先頭の空白ブロック等）も文字として
数えていたが、検出/マスク側 `PDFBlockTextMapper`／`detect_result["text"]` は空白のみ
ブロックをスキップする。マスク時は検出側の (block_num, offset) から
`block_start_global`（正準）でグローバルオフセットを計算し locator に渡すため、
両者の空間がずれてマスクが文字単位で左へずれていた（先頭の空白ブロック分だけ）。

本テストは、locator の `full_text_no_newlines` が正準ブロックテキストの連結と
一致することを保証する。
"""

import fitz

from src.pdf.pdf_block_mapper import PDFBlockTextMapper
from src.pdf.pdf_locator import PDFTextLocator


def _make_pdf_with_leading_and_inner_empty_blocks(path):
    """先頭と途中に空白のみブロックを含む合成PDFを作成する。"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 50), "   ")  # 先頭の空白のみブロック（不具合の主因）
    page.insert_text((72, 90), "Header")
    page.insert_text((72, 130), "   ")  # 途中の空白のみブロック
    page.insert_text((72, 170), "Address12345")
    page.insert_text((72, 210), "Row")
    doc.save(path)
    doc.close()


def _canonical_concat(doc):
    mapper = PDFBlockTextMapper(doc)
    parts = []
    for p in range(len(doc)):
        parts.extend(mapper.get_page_block_texts(p))
    return "".join(parts)


def test_locator_offset_space_matches_canonical(tmp_path):
    path = str(tmp_path / "empty_blocks.pdf")
    _make_pdf_with_leading_and_inner_empty_blocks(path)

    # フィクスチャが空白のみブロックを生むことを保証（生まないと不具合を再現できない）。
    raw = fitz.open(path)[0].get_text("rawdict")
    raw_blocks_with_lines = sum(1 for b in raw.get("blocks", []) if "lines" in b)
    canon_blocks = len(PDFBlockTextMapper(fitz.open(path)).get_page_block_texts(0))
    if raw_blocks_with_lines <= canon_blocks:
        import pytest

        pytest.skip("合成PDFが空白のみブロックを生成しなかった")

    canonical = _canonical_concat(fitz.open(path))
    locator = PDFTextLocator(fitz.open(path))

    # 長さも内容も正準連結と一致すること（= グローバルオフセット空間が同一）。
    assert len(locator.full_text_no_newlines) == len(canonical)
    assert locator.full_text_no_newlines == canonical


def test_canonical_global_offset_maps_to_correct_char(tmp_path):
    """正準 (block_start_global + 0) が locator 経由で住所先頭文字 'A' を指す。"""
    path = str(tmp_path / "empty_blocks2.pdf")
    _make_pdf_with_leading_and_inner_empty_blocks(path)

    doc = fitz.open(path)
    mapper = PDFBlockTextMapper(doc)
    block_texts = mapper.get_page_block_texts(0)

    # block_start_global を run_mask と同様に正準ブロックテキスト長から構築。
    block_start_global = {}
    cursor = 0
    for b, t in enumerate(block_texts):
        block_start_global[(0, b)] = cursor
        cursor += len(t)

    # 'Address12345' を含む正準ブロックを特定。
    addr_block = next(b for b, t in enumerate(block_texts) if "Address" in t)
    addr_offset_in_block = block_texts[addr_block].index("A")
    global_offset = block_start_global[(0, addr_block)] + addr_offset_in_block

    locator = PDFTextLocator(fitz.open(path))
    char_idx = locator.offset_to_char_mapping.get(global_offset)
    assert char_idx is not None
    assert locator.char_data[char_idx]["char"] == "A"
