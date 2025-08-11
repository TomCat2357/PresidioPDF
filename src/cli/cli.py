#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legacy subcommand-based CLI.
Note: New separate entrypoints exist: cli.read_main, cli.detect_main,
cli.duplicate_main, cli.mask_main. This module remains for backward
compatibility and delegates to the same implementations.
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
from core.config_manager import ConfigManager


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
    # Lazy import for fitz to avoid requiring it for unrelated subcommands
    import fitz  # PyMuPDF
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
    # Lazy import
    import fitz  # PyMuPDF
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
    # Lazy import to decouple from fitz when not needed
    from pdf.pdf_annotator import PDFAnnotator
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


@main.command("read", help="PDFを読み込み JSONを出力 (deprecated; use codex-read)")
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
    # Lazy imports
    import fitz  # PyMuPDF
    from pdf.pdf_locator import PDFTextLocator
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


@main.command("detect", help="read JSONからPIIを検出しJSON出力 (deprecated; use codex-detect)")
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
    # Lazy import to avoid heavy dependencies unless needed
    from analysis.analyzer import Analyzer
    analyzer = Analyzer(cfg)

    detections_plain: List[Dict[str, Any]] = []
    detections_struct: List[Dict[str, Any]] = []

    # Lazy imports
    import fitz  # PyMuPDF
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


@main.command("mask", help="検出JSONを使ってPDFにハイライト注釈を追加 (deprecated; use codex-mask)")
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

    from pdf.pdf_masker import PDFMasker  # Lazy import
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


@main.command("duplicate-process", help="検出結果の重複を処理して正規化 (deprecated; use codex-duplicate-process)")
@click.option("--detect", "detect_file", type=click.Path(exists=True), required=True)
@click.option(
    "--overlap",
    type=click.Choice(["exact", "contain", "overlap"]),
    default="overlap",
    show_default=True,
    help="重複の定義: exact=完全一致 / contain=包含 / overlap=一部重なり",
)
@click.option(
    "--keep",
    type=click.Choice(["widest", "first", "last", "entity-order"]),
    default="widest",
    show_default=True,
    help="グループから残す基準: widest=最も広い範囲 / first=先頭 / last=末尾 / entity-order=エンティティ優先順",
)
@click.option(
    "--entity-priority",
    type=str,
    help="entity-order用の優先順（CSV）。例: PERSON,EMAIL,PHONE",
)
@click.option("--out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
def dedupe_cmd(
    detect_file: str,
    overlap: str,
    keep: str,
    entity_priority: Optional[str],
    out: Optional[str],
    pretty: bool,
):
    data = json.loads(Path(detect_file).read_text(encoding="utf-8"))
    dets = data.get("detections", {}) or {}
    plain = dets.get("plain", []) or []
    struct = dets.get("structured", []) or []

    # 準備: エンティティ優先順マップ
    pri_map: Dict[str, int] = {}
    if entity_priority:
        pri = [p.strip() for p in entity_priority.split(",") if p.strip()]
        pri_map = {name: i for i, name in enumerate(pri)}

    # ヘルパー: 連結成分抽出
    def components(n: int, edges: List[Tuple[int, int]]):
        g = [[] for _ in range(n)]
        for a, b in edges:
            g[a].append(b); g[b].append(a)
        seen = [False] * n
        comps = []
        from collections import deque
        for i in range(n):
            if seen[i]:
                continue
            q = deque([i])
            seen[i] = True
            cur = []
            while q:
                v = q.popleft()
                cur.append(v)
                for w in g[v]:
                    if not seen[w]:
                        seen[w] = True
                        q.append(w)
            comps.append(cur)
        return comps

    # 判定: plain
    def interval_len(d):
        return max(0, int(d.get("end", 0)) - int(d.get("start", 0)))

    def plain_edges(items: List[Dict[str, Any]]):
        n = len(items)
        edges: List[Tuple[int, int]] = []
        if overlap == "exact":
            # 完全一致はキーでグルーピング
            sig_map: Dict[Tuple[int, int], List[int]] = {}
            for i, d in enumerate(items):
                key = (int(d.get("start", -1)), int(d.get("end", -1)))
                sig_map.setdefault(key, []).append(i)
            for idxs in sig_map.values():
                if len(idxs) > 1:
                    base = idxs[0]
                    for j in idxs[1:]:
                        edges.append((base, j))
            return n, edges
        # contain/overlap: O(n^2) 比較（典型投入は小規模想定）
        for i in range(n):
            si, ei = int(items[i].get("start", -1)), int(items[i].get("end", -1))
            for j in range(i + 1, n):
                sj, ej = int(items[j].get("start", -1)), int(items[j].get("end", -1))
                if overlap == "contain":
                    dup = (si <= sj and ej <= ei) or (sj <= si and ei <= ej)
                else:  # overlap
                    dup = (si <= ej) and (sj <= ei)
                if dup:
                    edges.append((i, j))
        return n, edges

    # 判定: structured
    from math import isclose

    def rect_area(q):
        x0, y0, x1, y1 = map(float, q)
        return max(0.0, (x1 - x0)) * max(0.0, (y1 - y0))

    def rect_intersects(a, b):
        ax0, ay0, ax1, ay1 = map(float, a)
        bx0, by0, bx1, by1 = map(float, b)
        ix0, iy0 = max(ax0, bx0), max(ay0, by0)
        ix1, iy1 = min(ax1, bx1), min(ay1, by1)
        return (ix1 - ix0) > 0 and (iy1 - iy0) > 0

    def rect_contains(outer, inner, eps=0.01):
        ox0, oy0, ox1, oy1 = map(float, outer)
        ix0, iy0, ix1, iy1 = map(float, inner)
        return (ix0 >= ox0 - eps and iy0 >= oy0 - eps and ix1 <= ox1 + eps and iy1 <= oy1 + eps)

    def norm_quads(quads: List[List[float]]):
        # 2桁丸め＋安定ソート
        rounded = [tuple(round(float(v), 2) for v in q) for q in (quads or [])]
        return tuple(sorted(rounded))

    def structured_edges(items: List[Dict[str, Any]]):
        n = len(items)
        edges: List[Tuple[int, int]] = []
        # ページ単位で比較を限定
        by_page: Dict[int, List[int]] = {}
        for i, d in enumerate(items):
            by_page.setdefault(int(d.get("page", 0)), []).append(i)
        for page, idxs in by_page.items():
            if overlap == "exact":
                sig_map: Dict[Tuple, List[int]] = {}
                for i in idxs:
                    sig = (page, norm_quads(items[i].get("quads", [])))
                    sig_map.setdefault(sig, []).append(i)
                for group in sig_map.values():
                    if len(group) > 1:
                        base = group[0]
                        for j in group[1:]:
                            edges.append((base, j))
                continue
            # contain / overlap: 任意ペアで条件を満たすと重複
            m = len(idxs)
            for a in range(m):
                ia = idxs[a]
                qa = items[ia].get("quads", []) or []
                for b in range(a + 1, m):
                    ib = idxs[b]
                    qb = items[ib].get("quads", []) or []
                    dup = False
                    if overlap == "contain":
                        # AがBに内包 または BがAに内包
                        def a_in_b(A, B):
                            return all(any(rect_contains(bq, aq) for bq in B) for aq in A)
                        dup = a_in_b(qa, qb) or a_in_b(qb, qa)
                    else:  # overlap
                        dup = any(rect_intersects(aq, bq) for aq in qa for bq in qb)
                    if dup:
                        edges.append((ia, ib))
        return n, edges

    # keepポリシー
    def choose_kept(idxs: List[int], items: List[Dict[str, Any]], kind: str) -> int:
        # kind: "plain" / "structured"
        if keep == "first":
            return idxs[0]
        if keep == "last":
            return idxs[-1]
        if keep == "entity-order":
            # 小さいpriorityが優先。未定義は大きな値。
            def prio(i):
                ent = str(items[i].get("entity", ""))
                return pri_map.get(ent, 10**9)
            best = min(idxs, key=lambda i: (prio(i), idxs.index(i)))
            return best
        # widest
        if kind == "plain":
            best = max(idxs, key=lambda i: (interval_len(items[i]), -idxs.index(i)))
        else:
            def total_area(i):
                return sum(rect_area(q) for q in (items[i].get("quads", []) or []))
            best = max(idxs, key=lambda i: (total_area(i), -idxs.index(i)))
        return best

    # 実行: plain
    n_p, e_p = plain_edges(plain)
    comps_p = components(n_p, e_p)
    kept_plain_idx = set(choose_kept(c, plain, "plain") for c in comps_p if c)
    plain_out = [d for i, d in enumerate(plain) if i in kept_plain_idx]

    # 実行: structured
    n_s, e_s = structured_edges(struct)
    comps_s = components(n_s, e_s)
    kept_struct_idx = set(choose_kept(c, struct, "structured") for c in comps_s if c)
    struct_out = [d for i, d in enumerate(struct) if i in kept_struct_idx]

    out_obj = data.copy()
    out_obj["detections"] = {"plain": plain_out, "structured": struct_out}
    _dump_json(out_obj, out, pretty)


if __name__ == "__main__":
    main()
