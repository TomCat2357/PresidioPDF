import importlib
import json

import fitz
import pytest
from click.testing import CliRunner

from src.cli.common import sha256_file
from src.cli.detect_main import main as detect_command
from src.cli.duplicate_main import main as duplicate_command
from src.cli.embed_main import main as embed_command
from src.cli.read_main import main as read_command


def _create_pdf(path, text="sample"):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_embed_main_accepts_force_and_prints_output_path(tmp_path, monkeypatch):
    runner = CliRunner()
    pdf_path = tmp_path / "input.pdf"
    json_path = tmp_path / "input.json"
    out_path = tmp_path / "output.pdf"
    _create_pdf(pdf_path, "embed")

    json_path.write_text(
        json.dumps(
            {
                "metadata": {"pdf": {"sha256": "different"}},
                "offset2coordsMap": {"0": {"0": [[1, 2, 3, 4]]}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    calls = []

    def fake_embed(original_pdf_path, output_pdf_path):
        calls.append((original_pdf_path, output_pdf_path))
        return True

    monkeypatch.setattr("src.cli.embed_main.embed_coordinate_map", fake_embed)

    result = runner.invoke(
        embed_command,
        [
            "--pdf",
            str(pdf_path),
            "-j",
            str(json_path),
            "--out",
            str(out_path),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert result.output.strip() == str(out_path)
    assert out_path.read_bytes() == pdf_path.read_bytes()
    assert calls == [(str(pdf_path), str(out_path))]


def test_embed_main_fails_when_coordinate_maps_are_missing(tmp_path):
    runner = CliRunner()
    pdf_path = tmp_path / "input.pdf"
    json_path = tmp_path / "input.json"
    out_path = tmp_path / "output.pdf"
    _create_pdf(pdf_path, "embed")

    json_path.write_text(
        json.dumps(
            {"metadata": {"pdf": {"sha256": sha256_file(str(pdf_path))}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        embed_command,
        ["--pdf", str(pdf_path), "-j", str(json_path), "--out", str(out_path)],
    )

    assert result.exit_code != 0
    assert "座標マップ" in result.output


def test_mask_main_force_and_embed_coordinates_keep_flow(tmp_path, monkeypatch):
    runner = CliRunner()
    pdf_path = tmp_path / "input.pdf"
    json_path = tmp_path / "input.json"
    out_path = tmp_path / "output.pdf"
    _create_pdf(pdf_path, "mask")

    json_path.write_text(
        json.dumps(
            {
                "metadata": {"pdf": {"sha256": "different"}},
                "detect": [],
                "text": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    mask_module = importlib.import_module("src.cli.mask_main")
    pdf_locator_module = importlib.import_module("src.pdf.pdf_locator")
    pdf_masker_module = importlib.import_module("src.pdf.pdf_masker")

    applied = []
    embedded = []

    class FakeConfigManager:
        def get_operation_mode(self):
            return "default"

    class FakePDFTextLocator:
        def __init__(self, doc):
            self.doc = doc

    class FakePDFMasker:
        def __init__(self, cfg):
            self.cfg = cfg

        def _apply_highlight_masking_with_mode(self, out, entities, mode):
            applied.append((out, entities, mode))

    def fake_embed(original_pdf_path, output_pdf_path):
        embedded.append((original_pdf_path, output_pdf_path))
        return True

    monkeypatch.setattr(mask_module, "ConfigManager", FakeConfigManager)
    monkeypatch.setattr(mask_module, "embed_coordinate_map", fake_embed)
    monkeypatch.setattr(pdf_locator_module, "PDFTextLocator", FakePDFTextLocator)
    monkeypatch.setattr(pdf_masker_module, "PDFMasker", FakePDFMasker)

    result = runner.invoke(
        mask_module.main,
        [
            "--pdf",
            str(pdf_path),
            "-j",
            str(json_path),
            "--out",
            str(out_path),
            "--force",
            "--embed-coordinates",
        ],
    )

    assert result.exit_code == 0
    assert result.output.strip() == str(out_path)
    assert out_path.read_bytes() == pdf_path.read_bytes()
    assert applied == [(str(out_path), [], "default")]
    assert embedded == [(str(pdf_path), str(out_path))]


@pytest.mark.parametrize(
    ("command", "expected_flags"),
    [
        (read_command, ["--pdf", "--out", "--pretty"]),
        (detect_command, ["-j, --json", "--out", "--pretty", "--validate"]),
        (duplicate_command, ["-j, --json", "--out", "--pretty", "--validate"]),
    ],
)
def test_cli_help_keeps_shared_options(command, expected_flags):
    runner = CliRunner()

    result = runner.invoke(command, ["--help"])

    assert result.exit_code == 0
    for flag in expected_flags:
        assert flag in result.output
