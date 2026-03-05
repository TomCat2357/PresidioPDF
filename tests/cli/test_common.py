import json

import click
import pytest

from src.cli.common import (
    copy_pdf_to_output,
    load_json_file,
    require_coordinate_maps,
    verify_pdf_hash,
)


def test_load_json_file_reads_utf8_json(tmp_path):
    json_path = tmp_path / "input.json"
    payload = {"text": "東京都千代田区", "count": 1}
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert load_json_file(str(json_path), "入力JSON") == payload


def test_load_json_file_wraps_decode_error(tmp_path):
    json_path = tmp_path / "broken.json"
    json_path.write_text("{", encoding="utf-8")

    with pytest.raises(click.ClickException, match="入力JSONの読み込みに失敗"):
        load_json_file(str(json_path), "入力JSON")


def test_verify_pdf_hash_raises_without_force(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"sample-pdf")

    with pytest.raises(click.ClickException, match="sha256"):
        verify_pdf_hash(
            str(pdf_path),
            {"pdf": {"sha256": "different"}},
            False,
            "PDFとJSONのsha256が一致しません (--force で無視)",
        )


def test_verify_pdf_hash_allows_force(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"sample-pdf")

    verify_pdf_hash(
        str(pdf_path),
        {"pdf": {"sha256": "different"}},
        True,
        "PDFとJSONのsha256が一致しません (--force で無視)",
    )


def test_copy_pdf_to_output_copies_bytes(tmp_path):
    src_path = tmp_path / "in.pdf"
    out_path = tmp_path / "nested" / "out.pdf"
    src_path.write_bytes(b"%PDF-1.4\nbody\n")

    copy_pdf_to_output(str(src_path), str(out_path))

    assert out_path.read_bytes() == src_path.read_bytes()


def test_require_coordinate_maps_raises_when_missing():
    with pytest.raises(click.ClickException, match="座標マップ"):
        require_coordinate_maps({}, "input.json")


def test_require_coordinate_maps_returns_existing_maps():
    payload = {
        "offset2coordsMap": {"0": {"0": [[1, 2, 3, 4]]}},
        "coords2offsetMap": {"0": {"0,0,1,1": 0}},
    }

    assert require_coordinate_maps(payload, "input.json") == (
        payload["offset2coordsMap"],
        payload["coords2offsetMap"],
    )
