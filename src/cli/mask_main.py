#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from core.config_manager import ConfigManager


def _validate_detect_json(obj: Dict[str, Any]) -> List[str]:
    errs = []
    if not isinstance(obj, dict):
        return ["root must be object"]
    src = obj.get("source", {}) or {}
    if not isinstance(src, dict):
        errs.append("source must be object")
    else:
        pdf = src.get("pdf", {}) or {}
        if not isinstance(pdf, dict) or not isinstance(pdf.get("sha256"), str):
            errs.append("source.pdf.sha256 must be string")
    dets = obj.get("detections", {}) or {}
    if not isinstance(dets, dict):
        errs.append("detections must be object")
    else:
        if "structured" in dets and dets["structured"] is not None:
            if not isinstance(dets["structured"], list):
                errs.append("detections.structured must be array")
    return errs


@click.command(help="検出JSONを使ってPDFにハイライト注釈を追加")
@click.argument("pdf", type=click.Path(exists=True))
@click.option("--detect", "detect_file", type=click.Path(exists=True), required=True)
@click.option("--force", is_flag=True, default=False, help="ハッシュ不一致でも続行")
@click.option("--label-only", is_flag=True, default=False, help="注釈に生テキストを含めない")
@click.option("--out", type=click.Path(), help="出力PDFパス（省略で規定出力名）")
@click.option("--validate", is_flag=True, default=False, help="検出JSONのスキーマ検証を実施")
def main(pdf: str, detect_file: str, force: bool, label_only: bool, out: Optional[str], validate: bool):
    cfg = ConfigManager()
    det = json.loads(Path(detect_file).read_text(encoding="utf-8"))
    if validate:
        errors = _validate_detect_json(det)
        if errors:
            raise click.ClickException("detect JSON validation failed: " + "; ".join(errors))

    # Validate hash against JSON reference when present
    from cli.common import sha256_file

    pdf_sha = sha256_file(pdf)
    ref_sha = ((det.get("source", {}) or {}).get("pdf", {}) or {}).get("sha256")
    if ref_sha and ref_sha != pdf_sha and not force:
        raise click.ClickException("PDFと検出JSONのsha256が一致しません (--force で無視)")

    # Build entities from structured detections
    entities: List[Dict[str, Any]] = []
    for st in (det.get("detections", {}) or {}).get("structured", []) or []:
        for q in st.get("quads", []) or []:
            entities.append(
                {
                    "entity_type": st.get("entity", "PII"),
                    "text": ("" if label_only else st.get("text", "")),
                    "line_rects": [
                        {
                            "rect": {"x0": float(q[0]), "y0": float(q[1]), "x1": float(q[2]), "y1": float(q[3])},
                            "page_num": max(0, int(st.get("page", 1)) - 1),
                        }
                    ],
                }
            )

    from pdf.pdf_masker import PDFMasker  # Lazy import

    masker = PDFMasker(cfg)
    output_path = None
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with open(pdf, "rb") as r, open(out, "wb") as w:
            w.write(r.read())
        masker._apply_highlight_masking_with_mode(out, entities, cfg.get_operation_mode())
        output_path = out
    else:
        output_path = masker.apply_masking(pdf, entities, masking_method="highlight")

    print(output_path)


if __name__ == "__main__":
    main()

