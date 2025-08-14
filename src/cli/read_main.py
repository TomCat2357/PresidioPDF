#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from core.config_manager import ConfigManager
from cli.common import dump_json, sha256_file, validate_input_file_exists, validate_output_parent_exists, validate_mutual_exclusion


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
@click.option("--pdf", type=str, required=True, help="入力PDFファイルのパス")
@click.option("--config", type=str, help="設定ファイル（readセクションのみ参照）")
@click.option("--out", type=str, help="出力先（未指定時は標準出力）")
@click.option("--pretty", is_flag=True, default=False, help="JSON整形出力")
@click.option("--validate", is_flag=True, default=False, help="入力の検証を実施")
@click.option("--with-highlights/--no-highlights", default=True, help="ハイライト情報を含める")
@click.option("--with-plain/--no-plain", default=True, help="プレーンテキストを含める")
@click.option("--with-structured/--no-structured", default=True, help="構造化テキストを含める")
def main(pdf: str, config: Optional[str], out: Optional[str], pretty: bool, validate: bool, with_highlights: bool, with_plain: bool, with_structured: bool):
    # ファイル存在確認
    validate_input_file_exists(pdf)
    if config:
        validate_input_file_exists(config)
    if out:
        validate_output_parent_exists(out)
    
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
