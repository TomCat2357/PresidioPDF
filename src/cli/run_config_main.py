#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_config_main.py - 設定ファイルに従って read/detect/duplicate/mask/embed を順次実行

CLIからの--config廃止に伴い、メタ的に設定ファイルを読んで
各サブコマンドにオプションを付与して実行する専用コマンド。
"""

from typing import Any, Dict, List, Tuple, Optional
from pathlib import Path
import sys

import click
import yaml


def _require_keys(obj: Dict[str, Any], keys: List[str], ctx: str):
    for k in keys:
        if k not in obj:
            raise click.ClickException(f"{ctx}: 必須キーがありません: {k}")


def _call_read(opts: Dict[str, Any]):
    from src.cli.read_main import main as read_main

    # 正規化
    pdf = opts.get("pdf")
    out = opts.get("out")
    pretty = bool(opts.get("pretty", False))
    with_map = opts.get("with_map", True)
    with_highlights = opts.get("with_highlights", True)
    log_level = opts.get("log_level")

    _require_keys({"pdf": pdf, "out": out}, ["pdf", "out"], "read")

    args: List[str] = ["--pdf", str(pdf), "--out", str(out)]
    if pretty:
        args.append("--pretty")
    if with_map is not None:
        args.append("--with-map" if with_map else "--no-map")
    if with_highlights is not None:
        args.append("--with-highlights" if with_highlights else "--no-highlights")
    if log_level:
        args.extend(["--log-level", str(log_level)])

    return read_main.main(args=args, standalone_mode=False)


def _call_detect(opts: Dict[str, Any]):
    from src.cli.detect_main import main as detect_main

    json_file = opts.get("json") or opts.get("json_file")
    out = opts.get("out")
    _require_keys({"json_file": json_file, "out": out}, ["json_file", "out"], "detect")

    adds = opts.get("adds") or opts.get("add") or []
    excludes = opts.get("excludes") or opts.get("exclude") or []
    model = opts.get("model") or []
    entities = opts.get("entities") or opts.get("entity")
    pretty = bool(opts.get("pretty", False))
    validate = bool(opts.get("validate", False))
    with_predetect = opts.get("with_predetect", True)
    use = opts.get("use")

    args: List[str] = ["-j", str(json_file), "--out", str(out)]
    for a in (adds if isinstance(adds, list) else [adds]):
        if a:
            args.extend(["--add", str(a)])
    for e in (excludes if isinstance(excludes, list) else [excludes]):
        if e:
            args.extend(["--exclude", str(e)])
    for m in (model if isinstance(model, list) else [model]):
        if m:
            args.extend(["--model", str(m)])
    if entities:
        args.extend(["--entity", str(entities)])
    if pretty:
        args.append("--pretty")
    if validate:
        args.append("--validate")
    if with_predetect is not None:
        args.append("--with-predetect" if with_predetect else "--no-predetect")
    if use:
        args.extend(["--use", str(use)])

    return detect_main.main(args=args, standalone_mode=False)


def _call_duplicate(opts: Dict[str, Any]):
    from src.cli.duplicate_main import main as duplicate_main

    json_file = opts.get("json") or opts.get("json_file")
    out = opts.get("out")
    _require_keys({"json_file": json_file, "out": out}, ["json_file", "out"], "duplicate")

    args: List[str] = ["-j", str(json_file), "--out", str(out)]
    def add_opt(flag: str, value: Optional[str]):
        if value is not None and value != "":
            args.extend([flag, str(value)])

    add_opt("--entity-order", opts.get("entity_order"))
    add_opt("--length-pref", opts.get("length_pref"))
    add_opt("--origin-priority", opts.get("origin_priority"))
    add_opt("--overlap", opts.get("overlap"))
    add_opt("--entity-overlap-mode", opts.get("entity_overlap_mode"))
    add_opt("--position-pref", opts.get("position_pref"))
    add_opt("--tie-break", opts.get("tie_break"))
    if bool(opts.get("pretty", False)):
        args.append("--pretty")
    if bool(opts.get("validate", False)):
        args.append("--validate")

    return duplicate_main.main(args=args, standalone_mode=False)


def _call_mask(opts: Dict[str, Any]):
    from src.cli.mask_main import main as mask_main

    json_file = opts.get("json") or opts.get("json_file")
    out = opts.get("out")
    pdf = opts.get("pdf")
    _require_keys({"json_file": json_file, "out": out, "pdf": pdf}, ["json_file", "out", "pdf"], "mask")

    args: List[str] = ["-j", str(json_file), "--out", str(out), "--pdf", str(pdf)]
    if bool(opts.get("force", False)):
        args.append("--force")
    if bool(opts.get("validate", False)):
        args.append("--validate")
    embed = opts.get("embed_coordinates", False)
    if embed is not None:
        args.append("--embed-coordinates" if embed else "--no-embed-coordinates")

    # エンティティ別マスク指定の伝搬（masks: ["PERSON=#FF0000@0.3", ...]）
    masks = opts.get("masks") or opts.get("mask")
    if masks:
        if isinstance(masks, list):
            for m in masks:
                args.extend(["--mask", str(m)])
        else:
            args.extend(["--mask", str(masks)])

    return mask_main.main(args=args, standalone_mode=False)


def _call_embed(opts: Dict[str, Any]):
    from src.cli.embed_main import main as embed_main

    json_file = opts.get("json") or opts.get("json_file")
    out = opts.get("out")
    pdf = opts.get("pdf")
    _require_keys({"json_file": json_file, "out": out, "pdf": pdf}, ["json_file", "out", "pdf"], "embed")

    args: List[str] = ["-j", str(json_file), "--out", str(out), "--pdf", str(pdf)]
    if bool(opts.get("force", False)):
        args.append("--force")
    return embed_main.main(args=args, standalone_mode=False)


OP_DISPATCH = {
    "read": _call_read,
    "detect": _call_detect,
    "duplicate": _call_duplicate,
    "mask": _call_mask,
    "embed": _call_embed,
}


@click.command(help="設定ファイルに従い read/detect/duplicate/mask/embed を順次実行するメタコマンド")
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, readable=True))
def main(config_path: str):
    cfg_path = Path(config_path)
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise click.ClickException(f"設定ファイルの読み込みに失敗しました: {e}")

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise click.ClickException("設定ファイルに steps: [] が必要です")

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise click.ClickException(f"steps[{i}] はオブジェクトである必要があります")
        op = step.get("op")
        opts = step.get("options") or {}
        if not isinstance(op, str) or not op:
            raise click.ClickException(f"steps[{i}].op は必須の文字列です")
        if not isinstance(opts, dict):
            raise click.ClickException(f"steps[{i}].options はオブジェクトである必要があります")

        op_l = op.strip().lower()
        if op_l not in OP_DISPATCH:
            allowed = ", ".join(OP_DISPATCH.keys())
            raise click.ClickException(f"不明なopです: {op}. 許可: {allowed}")

        click.echo(f"[{i+1}/{len(steps)}] 実行: {op_l}", err=True)
        OP_DISPATCH[op_l](opts)


if __name__ == "__main__":
    main()
