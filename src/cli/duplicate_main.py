#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path
from typing import Optional, Tuple, List

import click
import yaml

from cli.common import dump_json, validate_input_file_exists, validate_output_parent_exists
from core.dedupe import dedupe_detections
from core.config_manager import ConfigManager


@click.command(help="検出結果の重複を処理して正規化")
@click.option("--config", "shared_config", type=str, help="共通設定YAMLのパス（duplicateセクションのみ参照）")
@click.option("--entity-order", type=str, default="PERSON,PHONE_NUMBER,EMAIL_ADDRESS,ADDRESS,DATE_OF_BIRTH,CREDIT_CARD,PASSPORT,DRIVER_LICENSE,MYNUMBER,BANK_ACCOUNT", show_default=True, help="エンティティ優先順（カンマ区切り）")
@click.option("-j", "--json", "json_file", type=str, help="入力detect JSONファイル（未指定でstdin）")
@click.option("--length-pref", type=click.Choice(["long", "short"]), help="長短の優先: long/short")
@click.option("--origin-priority", type=str, default="manual,custom,auto", show_default=True, help="検出由来の優先順（カンマ区切り）")
@click.option("--out", type=str, help="出力先（未指定時は標準出力）")
@click.option("--overlap", type=click.Choice(["exact", "contain", "overlap"]), default="overlap", show_default=True, help="重複の定義: exact/contain/overlap")
@click.option("--position-pref", type=click.Choice(["first", "last"]), default="first", show_default=True, help="位置の優先: first/last（入力順ベース）")
@click.option("--pretty", is_flag=True, default=False, help="JSON整形出力")
@click.option("--tie-break", "tie_break", type=str, default="origin,length,position,entity", show_default=True, help="タイブレーク順（カンマ区切り）: origin,length,entity,position の並びで指定")
@click.option("--validate", is_flag=True, default=False, help="入力JSONの検証を実施")
def main(
    shared_config: Optional[str],
    entity_order: Optional[str],
    json_file: Optional[str],
    length_pref: Optional[str],
    origin_priority: Optional[str],
    out: Optional[str],
    overlap: str,
    position_pref: Optional[str],
    pretty: bool,
    tie_break: Optional[str],
    validate: bool,
):
    # ファイル存在確認
    if json_file:
        validate_input_file_exists(json_file)
    if shared_config:
        validate_input_file_exists(shared_config)
    if out:
        validate_output_parent_exists(out)
        
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
    ent_order = [p.strip() for p in (entity_order or ",".join(conf_entity_order)).split(",") if p.strip()]

    # 新しいタイブレークオプションを使用
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
    out_obj = data.copy()
    out_obj["detections"] = result
    dump_json(out_obj, out, pretty)


if __name__ == "__main__":
    main()
