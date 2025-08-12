#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path
from typing import Optional, Tuple, List

import click
import yaml

from cli.common import dump_json
from core.dedupe import dedupe_detections
from core.config_manager import ConfigManager


@click.command(help="検出結果の重複を処理して正規化")
@click.option("-j", "--json", "json_file", type=click.Path(exists=True), help="入力detect JSONファイル（未指定でstdin）")
@click.option("--pdf", type=click.Path(), required=False, help="IF統一のためのダミー（未使用）")
# 共有YAML（duplicate_processセクションのみ参照）
@click.option("--config", "shared_config", type=click.Path(exists=True), help="共通設定YAMLのパス（duplicate_processセクションのみ参照）")
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
    help="[従来] 残す基準: widest/first/last/entity-order（新オプション未指定時に使用）",
)
@click.option(
    "--entity-priority",
    type=str,
    help="[従来] entity-order用の優先順（CSV）",
)
# 新しいマルチ基準タイブレーク
@click.option(
    "--tie-break",
    "tie_break",
    type=str,
    help="タイブレーク順（CSV）: origin,length,entity,position の並びで指定",
)
@click.option(
    "--origin-priority",
    type=str,
    help="検出由来の優先順（CSV）: manual,addition,auto",
)
@click.option(
    "--length-pref",
    type=click.Choice(["long", "short"]),
    help="長短の優先: long/short",
)
@click.option(
    "--position-pref",
    type=click.Choice(["first", "last"]),
    help="位置の優先: first/last（入力順ベース）",
)
@click.option(
    "--entity-order",
    type=str,
    help="エンティティ優先順（CSV）",
)
@click.option("--out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
def main(
    json_file: Optional[str],
    pdf: Optional[str],
    shared_config: Optional[str],
    overlap: str,
    keep: str,
    entity_priority: Optional[str],
    tie_break: Optional[str],
    origin_priority: Optional[str],
    length_pref: Optional[str],
    position_pref: Optional[str],
    entity_order: Optional[str],
    out: Optional[str],
    pretty: bool,
):
    raw = Path(json_file).read_text(encoding="utf-8") if json_file else sys.stdin.read()
    data = json.loads(raw)

    # 共有YAMLから duplicate_process セクションを読み取り（引数で上書き）
    conf_tb: List[str] = []
    conf_origin_pri: List[str] = []
    conf_length: Optional[str] = None
    conf_position: Optional[str] = None
    conf_entity_order: List[str] = []
    if shared_config:
        try:
            with open(shared_config, "r", encoding="utf-8") as f:
                conf = yaml.safe_load(f) or {}
        except Exception as e:
            raise click.ClickException(f"--config の読み込みに失敗: {e}")
        dup_section = conf.get("duplicate_process") if isinstance(conf, dict) else None
        if dup_section is not None and not isinstance(dup_section, list):
            raise click.ClickException("config.yamlのduplicate_processセクションはリストである必要があります")
        if dup_section:
            for item in dup_section:
                if not isinstance(item, dict) or len(item) != 1:
                    continue
                (k, v), = item.items()
                k = str(k).strip()
                if k in ("tie_break", "tie-break"):
                    if isinstance(v, list):
                        conf_tb = [str(x).strip() for x in v if str(x).strip()]
                    elif isinstance(v, str):
                        conf_tb = [s.strip() for s in v.split(",") if s.strip()]
                elif k in ("origin_priority", "origin-priority"):
                    if isinstance(v, list):
                        conf_origin_pri = [str(x).strip() for x in v if str(x).strip()]
                    elif isinstance(v, str):
                        conf_origin_pri = [s.strip() for s in v.split(",") if s.strip()]
                elif k == "length":
                    conf_length = str(v).strip()
                elif k == "position":
                    conf_position = str(v).strip()
                elif k in ("entity_order", "entity-order"):
                    if isinstance(v, list):
                        conf_entity_order = [str(x).strip() for x in v if str(x).strip()]
                    elif isinstance(v, str):
                        conf_entity_order = [s.strip() for s in v.split(",") if s.strip()]

    # CLI引数で上書き
    tb = [s.strip() for s in (tie_break or ",".join(conf_tb)).split(",") if s.strip()] if (tie_break or conf_tb) else []
    origin_pri = [s.strip().lower() for s in (origin_priority or ",".join(conf_origin_pri)).split(",") if s.strip()] if (origin_priority or conf_origin_pri) else []
    length_pref_f = (length_pref or conf_length)
    position_pref_f = (position_pref or conf_position)
    ent_order = [p.strip() for p in (entity_order or ",".join(conf_entity_order) or (entity_priority or "")).split(",") if p.strip()]

    # 新オプションが指定されない場合は従来の引数にフォールバック
    use_new = bool(tb or origin_pri or length_pref_f or position_pref_f or ent_order)

    if use_new:
        result = dedupe_detections(
            data.get("detections", {}) or {},
            overlap=overlap,
            keep=None,
            entity_priority=ent_order,
            tie_break=tb,
            origin_priority=origin_pri,
            length_pref=length_pref_f,
            position_pref=position_pref_f,
        )
    else:
        pri = [p.strip() for p in (entity_priority or "").split(",") if p.strip()]
        result = dedupe_detections(
            data.get("detections", {}) or {}, overlap=overlap, keep=keep, entity_priority=pri
        )
    out_obj = data.copy()
    out_obj["detections"] = result
    dump_json(out_obj, out, pretty)


if __name__ == "__main__":
    main()
