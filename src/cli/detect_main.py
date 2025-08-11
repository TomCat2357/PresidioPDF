#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click

from core.config_manager import ConfigManager
from cli.common import dump_json, sha256_bytes, sha256_file


def _validate_read_json(obj: Dict[str, Any]) -> List[str]:
    errs = []
    if not isinstance(obj, dict):
        return ["root must be object"]
    src = obj.get("source", {}) or {}
    if not isinstance(src, dict):
        errs.append("source must be object")
    else:
        if not isinstance(src.get("path"), str) or not src.get("path"):
            errs.append("source.path must be non-empty string (absolute path)")
        for k in ["filename", "sha256"]:
            if not isinstance(src.get(k), str):
                errs.append(f"source.{k} must be string")
        if not isinstance(src.get("page_count"), int):
            errs.append("source.page_count must be int")
    content = obj.get("content", {}) or {}
    if not isinstance(content, dict):
        errs.append("content must be object")
    else:
        if "plain_text" in content and content["plain_text"] is not None and not isinstance(content["plain_text"], str):
            errs.append("content.plain_text must be string or null")
        if "structured_text" in content and content["structured_text"] is not None and not isinstance(content["structured_text"], dict):
            errs.append("content.structured_text must be object or null")
    return errs


def _detection_id(entity: str, text: str, payload: Tuple) -> str:
    raw = json.dumps([entity, text, payload], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(raw)


@click.command(help="read JSONからPIIを検出しJSON出力")
@click.option("--from", "src", type=click.Path(), help="read JSONファイル（省略でstdin）")
@click.option("--from-stdin", is_flag=True, default=False)
@click.option("--use-plain", is_flag=True, help="plain_textで検出を実行")
@click.option("--use-structured", is_flag=True, help="structured_textで検出を実行")
@click.option("--model", multiple=True, help="モデルID（未使用・将来拡張）")
@click.option("--add-entities", type=click.Path(exists=True), help="追加エンティティ定義ファイル（未実装）")
@click.option("--append-highlights/--no-append-highlights", default=True)
@click.option("--out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
@click.option("--validate", is_flag=True, default=False, help="入力JSONのスキーマ検証を実施")
def main(src: Optional[str], from_stdin: bool, use_plain: bool, use_structured: bool, model: Tuple[str, ...], add_entities: Optional[str], append_highlights: bool, out: Optional[str], pretty: bool, validate: bool):
    # load input JSON
    data_txt = Path(src).read_text(encoding="utf-8") if src else input()
    try:
        data = json.loads(data_txt)
    except Exception as e:
        raise click.ClickException(f"入力JSONの読み込みに失敗: {e}")

    if validate:
        errors = _validate_read_json(data)
        if errors:
            raise click.ClickException("read JSON validation failed: " + "; ".join(errors))

    pdf_path = data.get("source", {}).get("path")
    if not pdf_path or not Path(pdf_path).exists():
        raise click.ClickException("source.path にPDFの絶対パスが必要です（readの出力を使用してください）")

    plain_text = (data.get("content", {}) or {}).get("plain_text")
    use_plain = use_plain or (plain_text is not None and not use_structured)
    use_structured = use_structured or (plain_text is not None and not use_plain)
    if not (use_plain or use_structured):
        use_plain = plain_text is not None
        use_structured = True

    cfg = ConfigManager()
    from analysis.analyzer import Analyzer  # Lazy heavy dep

    analyzer = Analyzer(cfg)

    detections_plain: List[Dict[str, Any]] = []
    detections_struct: List[Dict[str, Any]] = []

    import fitz  # Lazy import
    from pdf.pdf_locator import PDFTextLocator

    with fitz.open(pdf_path) as doc:
        locator = PDFTextLocator(doc)
        target_text = plain_text if isinstance(plain_text, str) else locator.full_text_no_newlines
        enabled_entities = cfg.get_enabled_entities()
        model_results = analyzer.analyze_text(target_text, enabled_entities)

        for r in model_results:
            ent = r.get("entity_type") or r.get("entity")
            s = int(r["start"]); e = int(r["end"])  # codepoint offsets (no newlines)
            txt = target_text[s:e]
            did = _detection_id(ent, txt, (s, e))
            entry_plain = {
                "detection_id": did,
                "text": txt,
                "entity": ent,
                "start": s,
                "end": e,
                "unit": "codepoint",
                "origin": "model",
                "model_id": None,
                "confidence": r.get("confidence"),
            }
            if use_plain:
                detections_plain.append(entry_plain)
            if use_structured:
                quads = []
                for lr in locator.get_pii_line_rects(s, e):
                    rect = lr.get("rect") or {}
                    quads.append([rect.get("x0", 0.0), rect.get("y0", 0.0), rect.get("x1", 0.0), rect.get("y1", 0.0)])
                detections_struct.append({
                    "detection_id": did,
                    "text": txt,
                    "entity": ent,
                    "page": (locator.locate_pii_by_offset_no_newlines(s, e)[0]["page_num"] + 1) if locator.locate_pii_by_offset_no_newlines(s, e) else 1,
                    "quads": quads,
                    "origin": "model",
                    "model_id": None,
                    "confidence": r.get("confidence"),
                })

    out_obj = {
        "schema_version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": {
            "pdf": {"sha256": sha256_file(pdf_path)},
            "read_json_sha256": sha256_bytes(data_txt.encode("utf-8")),
        },
        "detections": {"plain": detections_plain, "structured": detections_struct},
    }
    if append_highlights:
        out_obj["highlights"] = (data.get("content", {}) or {}).get("highlight", [])
    dump_json(out_obj, out, pretty)


if __name__ == "__main__":
    main()

