#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import io
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from core.config_manager import ConfigManager
from cli.common import dump_json, sha256_file, validate_input_file_exists, validate_output_parent_exists


def _get_pdf_metadata(pdf_path: str) -> Dict[str, Any]:
    import fitz  # Lazy import

    p = Path(pdf_path)
    stat = p.stat()
    # MuPDFがstdout/stderrへ警告を出すことがあるため抑制
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        with fitz.open(pdf_path) as d:
            page_count = d.page_count
    return {
        "pdf": {
            "filename": p.name,
            "path": str(p.resolve()),
            "size": stat.st_size,
            "page_count": page_count,
            "sha256": sha256_file(pdf_path),
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _structured_from_pdf(pdf_path: str) -> Dict[str, Any]:
    import fitz  # Lazy import
    pages: List[Dict[str, Any]] = []
    # MuPDFの標準出力を抑制
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                raw = page.get_text("rawdict")
                out_blocks: List[Dict[str, Any]] = []
                for block in raw.get("blocks", []) or []:
                    if "lines" not in block:
                        continue
                    lines_out: List[Dict[str, Any]] = []
                    for line in block.get("lines", []) or []:
                        spans_out: List[Dict[str, Any]] = []
                        for span in line.get("spans", []) or []:
                            spans_out.append({"text": span.get("text", ""), "bbox": span.get("bbox", None)})
                        if spans_out:
                            lines_out.append({"spans": spans_out})
                    if lines_out:
                        out_blocks.append({"lines": lines_out})
                pages.append({"page": i + 1, "blocks": out_blocks})
    return {"pages": pages}


def _blocks_plain_text(structured: Dict[str, Any]) -> List[str]:
    blocks_out: List[str] = []
    for page in (structured.get("pages", []) or []):
        for block in (page.get("blocks", []) or []):
            parts: List[str] = []
            for line in (block.get("lines", []) or []):
                for span in (line.get("spans", []) or []):
                    parts.append(str(span.get("text", "")))
            if parts:
                blocks_out.append("".join(parts))
    return blocks_out


def _read_highlight_raw(pdf_path: str, cfg: ConfigManager) -> List[Dict[str, Any]]:
    """PDFAnnotatorのそのままの出力からHighlightのみを返す（テスト期待仕様）。"""
    from pdf.pdf_annotator import PDFAnnotator

    annot = PDFAnnotator(cfg)
    # MuPDFの標準出力を抑制
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        anns = annot.read_pdf_annotations(pdf_path)
    return [a for a in (anns or []) if a.get("annotation_type") == "Highlight"]


@click.command(help="PDFを読み込み 統一スキーマのJSONをファイル出力（text.*, detect.*）")
@click.option("--pdf", type=str, required=True, help="入力PDFファイルのパス")
@click.option("--config", type=str, help="設定ファイル（readセクションのみ参照）")
@click.option("--out", type=str, required=True, help="出力先（必ず指定。標準出力は不可）")
@click.option("--pretty", is_flag=True, default=False, help="JSON整形出力")
@click.option("--with-highlights/--no-highlights", default=True, help="既存ハイライトをdetect.structuredに含める")
@click.option("--with-plain/--no-plain", default=True, help="text.plain（ブロック配列）を含める")
@click.option("--with-structured/--no-structured", default=True, help="text.structuredを含める")
def main(pdf: str, config: Optional[str], out: Optional[str], pretty: bool, with_highlights: bool, with_plain: bool, with_structured: bool):
    try:
        # 入力確認
        validate_input_file_exists(pdf)
        if out:
            validate_output_parent_exists(out)

        cfg = ConfigManager()

        metadata = _get_pdf_metadata(pdf)
        text_obj: Dict[str, Any] = {}
        detect_obj: Dict[str, Any] = {}

        if with_structured:
            structured = _structured_from_pdf(pdf)
            text_obj["structured"] = structured
            if with_plain:
                text_obj["plain"] = _blocks_plain_text(structured)
        elif with_plain:
            text_obj["plain"] = []

        if with_highlights:
            detect_obj["structured"] = _read_highlight_raw(pdf, cfg)

        result: Dict[str, Any] = {"metadata": metadata}
        if text_obj:
            result["text"] = text_obj
        # detectは空でもキーを用意（統一スキーマ準拠）
        result["detect"] = detect_obj if detect_obj else {"structured": []}
        dump_json(result, out, pretty)
    except Exception as e:
        # 例外でもファイルにJSONで返す
        err = {"metadata": {"error": str(e)}, "text": {}, "detect": {"structured": []}}
        # out は必須指定のため、そのまま書き出し
        dump_json(err, out, pretty)


if __name__ == "__main__":
    main()
