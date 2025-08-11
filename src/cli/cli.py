#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Subcommand-based CLI per cli_modify.md

Commands:
  - read: read PDF -> JSON (highlights/plain/structured)
  - detect: detect PII from read JSON -> JSON (plain offsets / structured quads)
  - mask: apply highlight annotations using detect JSON
  - duplicate-process: de-duplicate detect JSON per simple policy
"""
import json
import logging
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import fitz  # PyMuPDF

from core.config_manager import ConfigManager
from analysis.analyzer import Analyzer
from pdf.pdf_locator import PDFTextLocator
from pdf.pdf_processor import PDFProcessor
from pdf.pdf_masker import PDFMasker
from pdf.pdf_annotator import PDFAnnotator


def _dump_json(obj: Any, out_path: Optional[str], pretty: bool):
    text = json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None)
    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        click.echo(text)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_pdf_source_info(pdf_path: str) -> Dict[str, Any]:
    p = Path(pdf_path)
    stat = p.stat()
    with fitz.open(pdf_path) as d:
        page_count = d.page_count
    return {
        "filename": p.name,
        "path": str(p.resolve()),
        "size": stat.st_size,
        "page_count": page_count,
        "sha256": _sha256_file(pdf_path),
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def _structured_from_pdf(pdf_path: str) -> Dict[str, Any]:
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
                        spans_out.append(
                            {
                                "text": span.get("text", ""),
                                "bbox": span.get("bbox", None),
                            }
                        )
                    if spans_out:
                        lines_out.append({"spans": spans_out})
                if lines_out:
                    out_blocks.append({"lines": lines_out})
            pages.append({"page": i + 1, "blocks": out_blocks})
    return {"pages": pages}


def _read_highlights(pdf_path: str, cfg: ConfigManager) -> List[Dict[str, Any]]:
    annot = PDFAnnotator(cfg)
    return annot.read_pdf_annotations(pdf_path)


@click.group()
@click.option("--verbose", "-v", count=True, help="詳細ログの段階的有効化 (-v, -vv)")
@click.option("--quiet", is_flag=True, default=False, help="出力を抑制")
@click.option("--config", type=click.Path(exists=True), help="設定ファイル")
def main(verbose: int, quiet: bool, config: Optional[str]):
    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)
    logging.getLogger().setLevel(level)
    # store in click context if needed later


@main.command("read", help="PDFを読み込み JSONを出力")
@click.argument("pdf", type=click.Path(exists=True))
@click.option("--with-highlights/--no-highlights", default=True)
@click.option("--with-plain/--no-plain", default=True)
@click.option("--with-structured/--no-structured", default=True)
@click.option("--norm-coords", is_flag=True, default=False, help="将来拡張用")
@click.option("--out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
def read_cmd(pdf: str, with_highlights: bool, with_plain: bool, with_structured: bool, norm_coords: bool, out: Optional[str], pretty: bool):
    cfg = ConfigManager()
    result: Dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": _get_pdf_source_info(pdf),
        "content": {},
    }
    # highlights
    if with_highlights:
        result["content"]["highlight"] = _read_highlights(pdf, cfg)
    # texts
    with fitz.open(pdf) as doc:
        locator = PDFTextLocator(doc)
        if with_plain:
            result["content"]["plain_text"] = locator.full_text_no_newlines
        if with_structured:
            result["content"]["structured_text"] = _structured_from_pdf(pdf)
    _dump_json(result, out, pretty)


def _detection_id(entity: str, text: str, payload: Tuple) -> str:
    raw = json.dumps([entity, text, payload], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(raw)


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
        # plain validations
        if "plain" in dets and dets["plain"] is not None:
            if not isinstance(dets["plain"], list):
                errs.append("detections.plain must be array")
            else:
                for i, item in enumerate(dets["plain"]):
                    if not isinstance(item, dict):
                        errs.append(f"detections.plain[{i}] must be object"); continue
                    for k in ["detection_id", "text", "entity", "unit", "origin"]:
                        if not isinstance(item.get(k), str):
                            errs.append(f"detections.plain[{i}].{k} must be string")
                    for k in ["start", "end"]:
                        if not isinstance(item.get(k), int):
                            errs.append(f"detections.plain[{i}].{k} must be int")
                    s, e = item.get("start"), item.get("end")
                    if isinstance(s, int) and isinstance(e, int) and not (s < e):
                        errs.append(f"detections.plain[{i}] start must be < end")
        # structured validations
        if "structured" in dets and dets["structured"] is not None:
            if not isinstance(dets["structured"], list):
                errs.append("detections.structured must be array")
            else:
                for i, item in enumerate(dets["structured"]):
                    if not isinstance(item, dict):
                        errs.append(f"detections.structured[{i}] must be object"); continue
                    for k in ["detection_id", "text", "entity"]:
                        if not isinstance(item.get(k), str):
                            errs.append(f"detections.structured[{i}].{k} must be string")
                    if not isinstance(item.get("page"), int) or item.get("page", 0) < 1:
                        errs.append(f"detections.structured[{i}].page must be int >= 1")
                    quads = item.get("quads")
                    if not isinstance(quads, list) or not quads:
                        errs.append(f"detections.structured[{i}].quads must be non-empty array")
                    else:
                        for j, q in enumerate(quads):
                            if not (isinstance(q, (list, tuple)) and len(q) == 4 and all(isinstance(x, (int, float)) for x in q)):
                                errs.append(f"detections.structured[{i}].quads[{j}] must be [x0,y0,x1,y1] numbers")
    return errs


@main.command("detect", help="read JSONからPIIを検出しJSON出力")
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
def detect_cmd(src: Optional[str], from_stdin: bool, use_plain: bool, use_structured: bool, model: Tuple[str, ...], add_entities: Optional[str], append_highlights: bool, out: Optional[str], pretty: bool, validate: bool):
    # load input JSON
    data_txt = None
    if src:
        data_txt = Path(src).read_text(encoding="utf-8")
    else:
        data_txt = sys.stdin.read()
    try:
        data = json.loads(data_txt)
    except Exception as e:
        raise click.ClickException(f"入力JSONの読み込みに失敗: {e}")

    if validate:
        errors = _validate_read_json(data)
        if errors:
            raise click.ClickException("read JSON validation failed: " + "; ".join(errors))

    pdf_path = data.get("source", {}).get("path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise click.ClickException("source.path にPDFの絶対パスが必要です（readの出力を使用してください）")

    plain_text = (data.get("content", {}) or {}).get("plain_text")
    use_plain = use_plain or (plain_text is not None and not use_structured)
    use_structured = use_structured or (plain_text is not None and not use_plain)
    # default: if neither specified, use both when available
    if not (use_plain or use_structured):
        use_plain = plain_text is not None
        use_structured = True

    cfg = ConfigManager()
    analyzer = Analyzer(cfg)

    detections_plain: List[Dict[str, Any]] = []
    detections_struct: List[Dict[str, Any]] = []

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
            "pdf": {"sha256": _sha256_file(pdf_path)},
            "read_json_sha256": _sha256_bytes(data_txt.encode("utf-8")),
        },
        "detections": {
            "plain": detections_plain,
            "structured": detections_struct,
        },
    }
    if append_highlights:
        out_obj["highlights"] = (data.get("content", {}) or {}).get("highlight", [])
    _dump_json(out_obj, out, pretty)


@main.command("mask", help="検出JSONを使ってPDFにハイライト注釈を追加")
@click.argument("pdf", type=click.Path(exists=True))
@click.option("--detect", "detect_file", type=click.Path(exists=True), required=True)
@click.option("--force", is_flag=True, default=False, help="ハッシュ不一致でも続行")
@click.option("--label-only", is_flag=True, default=False, help="注釈に生テキストを含めない")
@click.option("--out", type=click.Path(), help="出力PDFパス（省略で規定出力名）")
@click.option("--validate", is_flag=True, default=False, help="検出JSONのスキーマ検証を実施")
def mask_cmd(pdf: str, detect_file: str, force: bool, label_only: bool, out: Optional[str], validate: bool):
    cfg = ConfigManager()
    # hash validation
    det = json.loads(Path(detect_file).read_text(encoding="utf-8"))
    if validate:
        errors = _validate_detect_json(det)
        if errors:
            raise click.ClickException("detect JSON validation failed: " + "; ".join(errors))
    pdf_sha = _sha256_file(pdf)
    ref_sha = ((det.get("source", {}) or {}).get("pdf", {}) or {}).get("sha256")
    if ref_sha and ref_sha != pdf_sha and not force:
        raise click.ClickException("PDFと検出JSONのsha256が一致しません (--force で無視)")

    # build entities in expected structure for PDFMasker (line_rects)
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

    masker = PDFMasker(cfg)
    # If out specified, temporarily override output_dir by environment
    output_path = None
    if out:
        # Write to a copy at `out`
        tmp = masker._generate_output_path(pdf)
        output_path = out
        # copy source to exact out path first
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with open(pdf, "rb") as r, open(out, "wb") as w:
            w.write(r.read())
        # now apply highlights in-place on out
        masker._apply_highlight_masking_with_mode(out, entities, cfg.get_operation_mode())
    else:
        output_path = masker.apply_masking(pdf, entities, masking_method="highlight")
    click.echo(output_path)


def _dedupe_list(items: List[Dict[str, Any]], key_fn) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        k = key_fn(it)
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


@main.command("duplicate-process", help="検出結果の重複を処理して正規化")
@click.option("--detect", "detect_file", type=click.Path(exists=True), required=True)
@click.option("--policy", type=click.Path(exists=True), help="未実装: ポリシーファイル")
@click.option("--entity-priority", type=str, help="未実装: エンティティ優先順")
@click.option("--keep", type=click.Choice(["origin", "longest", "highest-priority"]), default="origin")
@click.option("--out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
def dedupe_cmd(detect_file: str, policy: Optional[str], entity_priority: Optional[str], keep: str, out: Optional[str], pretty: bool):
    data = json.loads(Path(detect_file).read_text(encoding="utf-8"))
    dets = data.get("detections", {}) or {}
    plain = dets.get("plain", []) or []
    struct = dets.get("structured", []) or []

    plain_dedup = _dedupe_list(
        plain,
        key_fn=lambda d: (d.get("entity"), d.get("text"), int(d.get("start", -1)), int(d.get("end", -1))),
    )
    struct_dedup = _dedupe_list(
        struct,
        key_fn=lambda d: (d.get("entity"), d.get("text"), int(d.get("page", 0)), tuple(tuple(map(float, q)) for q in (d.get("quads", []) or []))),
    )

    out_obj = data.copy()
    out_obj["detections"] = {"plain": plain_dedup, "structured": struct_dedup}
    _dump_json(out_obj, out, pretty)


if __name__ == "__main__":
    main()
