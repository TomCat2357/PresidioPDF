#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sys

import click
import yaml

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
@click.option("--add", "adds", multiple=True, help="追加エンティティ: --add <entity>:<regex>（複数可）")
@click.option("--config", "shared_config", type=click.Path(exists=True), help="共通設定YAMLのパス（detectセクションのみ参照）")
@click.option("--exclude", "excludes", multiple=True, help="全エンティティ共通の除外正規表現（複数可）")
@click.option("-j", "--json", "json_file", type=click.Path(exists=True), help="入力read JSONファイル（未指定でstdin）")
@click.option("--model", multiple=True, help="モデルID（未使用・将来拡張）")
@click.option("--out", type=click.Path(), help="出力先（未指定時は標準出力）")
@click.option("--pretty", is_flag=True, default=False, help="JSON整形出力")
@click.option("--use", type=click.Choice(["plain", "structured", "both", "auto"]), default="auto", help="検出対象の選択")
@click.option("--validate", is_flag=True, default=False, help="入力JSONのスキーマ検証を実施")
@click.option("--append-highlights/--no-append-highlights", default=True, help="追加ハイライトを付与／抑止")
def main(adds: Tuple[str, ...], shared_config: Optional[str], excludes: Tuple[str, ...], json_file: Optional[str], model: Tuple[str, ...], out: Optional[str], pretty: bool, use: str, validate: bool, append_highlights: bool):
    # load input JSON (-j指定時はファイル、未指定時はstdin)
    data_txt = Path(json_file).read_text(encoding="utf-8") if json_file else sys.stdin.read()
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
    # --useオプションによる処理対象の決定
    if use == "plain":
        use_plain, use_structured = True, False
    elif use == "structured":
        use_plain, use_structured = False, True
    elif use == "both":
        use_plain, use_structured = True, True
    else:  # auto
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

        # 共有YAMLからdetectセクションを読み取り（引数優先でマージ）
        config_adds: List[Tuple[str, str]] = []  # (ENTITY, regex)
        config_excludes: List[str] = []
        if shared_config:
            try:
                with open(shared_config, "r", encoding="utf-8") as f:
                    conf = yaml.safe_load(f) or {}
            except Exception as e:
                raise click.ClickException(f"--config の読み込みに失敗: {e}")
            detect_section = conf.get("detect") if isinstance(conf, dict) else None
            if detect_section is not None and not isinstance(detect_section, list):
                raise click.ClickException("config.yamlのdetectセクションはリストである必要があります")

            # エンティティ許容（厳密）: 小文字→内部表記
            entity_aliases = {
                "person": "PERSON",
                "location": "LOCATION",
                "date_time": "DATE_TIME",
                "phone_number": "PHONE_NUMBER",
                "individual_number": "INDIVIDUAL_NUMBER",
                "year": "YEAR",
                "proper_noun": "PROPER_NOUN",
            }

            if detect_section:
                for item in detect_section:
                    if not isinstance(item, dict):
                        continue
                    if "entities" in item:
                        ents = item.get("entities") or []
                        if not isinstance(ents, list):
                            raise click.ClickException("detect.entities はリストである必要があります")
                        for ent_item in ents:
                            if not isinstance(ent_item, dict) or len(ent_item) != 1:
                                raise click.ClickException("entities 配下は {<entity>: <regex>} 形式で指定してください")
                            (k, v), = ent_item.items()
                            if not isinstance(v, str) or not v:
                                raise click.ClickException("entities の正規表現は非空文字列である必要があります")
                            k_l = str(k).strip().lower()
                            if k_l not in entity_aliases:
                                raise click.ClickException(f"未定義のエンティティ種別です: {k}")
                            config_adds.append((entity_aliases[k_l], v))
                    if "exclude" in item:
                        exs = item.get("exclude") or []
                        if not isinstance(exs, list):
                            raise click.ClickException("detect.exclude はリストである必要があります")
                        for rx in exs:
                            if not isinstance(rx, str) or not rx:
                                raise click.ClickException("exclude の正規表現は非空文字列である必要があります")
                            config_excludes.append(rx)

        # 引数 --add / --exclude をパース（引数優先: 並び順維持のため先頭に）
        def parse_add_arg(s: str) -> Tuple[str, str]:
            if ":" not in s:
                raise click.ClickException("--add は <entity>:<regex> 形式で指定してください")
            ent_name, regex = s.split(":", 1)
            ent_key = ent_name.strip().lower()
            aliases = {
                "person": "PERSON",
                "location": "LOCATION",
                "date_time": "DATE_TIME",
                "phone_number": "PHONE_NUMBER",
                "individual_number": "INDIVIDUAL_NUMBER",
                "year": "YEAR",
                "proper_noun": "PROPER_NOUN",
            }
            if ent_key not in aliases:
                raise click.ClickException(f"未定義のエンティティ種別です: {ent_name}")
            if not regex:
                raise click.ClickException("--add の正規表現が空です")
            return aliases[ent_key], regex

        cli_adds: List[Tuple[str, str]] = [parse_add_arg(a) for a in adds]
        cli_excludes: List[str] = list(excludes)

        # 結合（引数が先、次にconfig）
        add_specs: List[Tuple[str, str]] = cli_adds + config_adds
        exclude_specs: List[str] = cli_excludes + config_excludes

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

        # 追加の正規表現での検出（origin: addition）
        compiled_adds: List[Tuple[str, re.Pattern]] = []
        for ent_name, rx in add_specs:
            try:
                compiled_adds.append((ent_name, re.compile(rx)))
            except re.error as e:
                raise click.ClickException(f"無効な追加正規表現です: {rx}: {e}")

        for ent_name, rx in compiled_adds:
            for m in rx.finditer(target_text):
                s, e = m.start(), m.end()
                txt = target_text[s:e]
                did = _detection_id(ent_name, txt, (s, e))
                if use_plain:
                    detections_plain.append({
                        "detection_id": did,
                        "text": txt,
                        "entity": ent_name,
                        "start": s,
                        "end": e,
                        "unit": "codepoint",
                        "origin": "addition",
                        "model_id": None,
                        "confidence": None,
                    })
                if use_structured:
                    quads = []
                    for lr in locator.get_pii_line_rects(s, e):
                        rect = lr.get("rect") or {}
                        quads.append([rect.get("x0", 0.0), rect.get("y0", 0.0), rect.get("x1", 0.0), rect.get("y1", 0.0)])
                    detections_struct.append({
                        "detection_id": did,
                        "text": txt,
                        "entity": ent_name,
                        "page": (locator.locate_pii_by_offset_no_newlines(s, e)[0]["page_num"] + 1) if locator.locate_pii_by_offset_no_newlines(s, e) else 1,
                        "quads": quads,
                        "origin": "addition",
                        "model_id": None,
                        "confidence": None,
                    })

        # 除外正規表現にマッチする範囲（span）を収集
        compiled_excludes: List[re.Pattern] = []
        for rx in exclude_specs:
            try:
                compiled_excludes.append(re.compile(rx))
            except re.error as e:
                raise click.ClickException(f"無効な除外正規表現です: {rx}: {e}")

        exclude_spans: List[Tuple[int, int]] = []
        for rx in compiled_excludes:
            for m in rx.finditer(target_text):
                exclude_spans.append((m.start(), m.end()))

        # 追加 > 除外 > 自動検出: 除外は自動検出（origin=model）のみから除去
        if exclude_spans:
            def overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
                return max(a[0], b[0]) < min(a[1], b[1])

            def is_model(entry: Dict[str, Any]) -> bool:
                return entry.get("origin") == "model"

            detections_plain = [
                d for d in detections_plain
                if (not is_model(d)) or (not any(overlaps((d.get("start", 0), d.get("end", 0)), es) for es in exclude_spans))
            ]
            # structured は start/end を持たないため、plainと同一IDを参照して除外
            plain_ids_after = {d["detection_id"] for d in detections_plain}
            detections_struct = [d for d in detections_struct if (d.get("origin") != "model") or (d.get("detection_id") in plain_ids_after)]

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
