#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Optional, Tuple, List

import click

from cli.common import dump_json
from cli.duplicate_utils import dedupe_detections


@click.command(help="検出結果の重複を処理して正規化")
@click.option("--detect", "detect_file", type=click.Path(exists=True), required=True)
@click.option(
    "--overlap",
    type=click.Choice(["exact", "contain", "overlap"]),
    default="overlap",
    show_default=True,
    help="重複の定義: exact/contain/overlap",
)
@click.option(
    "--keep",
    type=click.Choice(["widest", "first", "last", "entity-order"]),
    default="widest",
    show_default=True,
    help="残す基準: widest/first/last/entity-order",
)
@click.option(
    "--entity-priority",
    type=str,
    help="entity-order用の優先順（CSV）",
)
@click.option("--out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
def main(detect_file: str, overlap: str, keep: str, entity_priority: Optional[str], out: Optional[str], pretty: bool):
    data = json.loads(Path(detect_file).read_text(encoding="utf-8"))
    pri = [p.strip() for p in (entity_priority or "").split(",") if p.strip()]
    result = dedupe_detections(data.get("detections", {}) or {}, overlap=overlap, keep=keep, entity_priority=pri)
    out_obj = data.copy()
    out_obj["detections"] = result
    dump_json(out_obj, out, pretty)


if __name__ == "__main__":
    main()

