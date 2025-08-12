#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from core.config_manager import ConfigManager
from cli.common import dump_json, sha256_file


def _get_pdf_source_info(pdf_path: str) -> Dict[str, Any]:
    import fitz  # Lazy import

    p = Path(pdf_path)
    stat = p.stat()
    with fitz.open(pdf_path) as d:
        page_count = d.page_count
    return {
        "filename": p.name,
        "path": str(p.resolve()),
        "size": stat.st_size,
        "page_count": page_count,
        "sha256": sha256_file(pdf_path),
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def _structured_from_pdf(pdf_path: str) -> Dict[str, Any]:
    import fitz  # Lazy import

    pages: List[Dict[str, Any]] = []
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


def _read_highlights(pdf_path: str, cfg: ConfigManager) -> List[Dict[str, Any]]:
    from pdf.pdf_annotator import PDFAnnotator

    annot = PDFAnnotator(cfg)
    return annot.read_pdf_annotations(pdf_path)


@click.command(help="PDFを読み込み JSONを出力")
@click.option("--pdf", "pdf", type=click.Path(exists=True), required=True, help="入力PDFファイルのパス")
@click.option("-j", "--json", is_flag=True, default=False, help="互換のためのダミーフラグ（効果なし）")
@click.option("--with-highlights/--no-highlights", default=True)
@click.option("--with-plain/--no-plain", default=True)
@click.option("--with-structured/--no-structured", default=True)
@click.option("--norm-coords", is_flag=True, default=False, help="将来拡張用")
@click.option("--out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
def main(pdf: str, json: bool, with_highlights: bool, with_plain: bool, with_structured: bool, norm_coords: bool, out: Optional[str], pretty: bool):
    cfg = ConfigManager()
    result: Dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": _get_pdf_source_info(pdf),
        "content": {},
    }
    if with_highlights:
        result["content"]["highlight"] = _read_highlights(pdf, cfg)

    import fitz  # Lazy import
    from pdf.pdf_locator import PDFTextLocator

    with fitz.open(pdf) as doc:
        locator = PDFTextLocator(doc)
        if with_plain:
            result["content"]["plain_text"] = locator.full_text_no_newlines
        if with_structured:
            result["content"]["structured_text"] = _structured_from_pdf(pdf)

    dump_json(result, out, pretty)


if __name__ == "__main__":
    main()
