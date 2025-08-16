#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path
from typing import Optional, Tuple, List

import click

from src.cli.common import dump_json, validate_input_file_exists, validate_output_parent_exists
from src.core.dedupe import dedupe_detections
from src.core.config_manager import ConfigManager


# 許可されたエンティティリスト（仕様で固定）
ALLOWED_ENTITY_NAMES = [
    "PERSON", "LOCATION", "DATE_TIME", "PHONE_NUMBER", 
    "INDIVIDUAL_NUMBER", "YEAR", "PROPER_NOUN", "OTHER"
]

def _dedupe_detections_spec_format(
    detect_list: List,
    overlap: str,
    entity_overlap_mode: str,
    entity_priority: List[str],
    tie_break: List[str],
    origin_priority: List[str],
    length_pref: Optional[str],
    position_pref: Optional[str],
) -> List:
    """仕様書形式の重複処理実装"""
    if not detect_list:
        return []
    
    # 簡略化された重複処理ロジック
    result = []
    processed_indices = set()
    
    for i, item in enumerate(detect_list):
        if i in processed_indices:
            continue
            
        # 重複するアイテムを探す
        duplicates = [i]
        for j, other in enumerate(detect_list[i+1:], i+1):
            if j in processed_indices:
                continue
                
            # エンティティタイプチェック
            if entity_overlap_mode == "same" and item.get("entity") != other.get("entity"):
                continue
                
            # 位置の重複チェック（簡略化）
            if _positions_overlap(item, other, overlap):
                duplicates.append(j)
        
        # 重複グループから最適を選択
        best_item = _select_best_item([detect_list[idx] for idx in duplicates], tie_break, origin_priority, length_pref, entity_priority)
        result.append(best_item)
        
        processed_indices.update(duplicates)
    
    return result


def _positions_overlap(item1, item2, overlap_mode: str) -> bool:
    """位置の重複をチェック（簡略化）"""
    # 仕様書形式ではstart/endがpage_num,block_num,offset形式
    start1 = item1.get("start", {})
    end1 = item1.get("end", {})
    start2 = item2.get("start", {})
    end2 = item2.get("end", {})
    
    # 簡略化: 同じページ・ブロック内でオフセットが重複しているかをチェック
    if (start1.get("page_num") == start2.get("page_num") and 
        start1.get("block_num") == start2.get("block_num")):
        
        offset1_start = start1.get("offset", 0)
        offset1_end = end1.get("offset", 0)
        offset2_start = start2.get("offset", 0)
        offset2_end = end2.get("offset", 0)
        
        if overlap_mode == "exact":
            return offset1_start == offset2_start and offset1_end == offset2_end
        elif overlap_mode == "contain":
            return (offset1_start <= offset2_start <= offset1_end) or (offset2_start <= offset1_start <= offset2_end)
        else:  # overlap
            return max(offset1_start, offset2_start) < min(offset1_end, offset2_end)
    
    return False


def _select_best_item(items, tie_break: List[str], origin_priority: List[str], length_pref: Optional[str], entity_priority: List[str]):
    """重複グループから最適アイテムを選択"""
    if len(items) == 1:
        return items[0]
    
    # 簡略化されたタイブレークロジック
    best = items[0]
    for item in items[1:]:
        if _is_better(item, best, tie_break, origin_priority, length_pref, entity_priority):
            best = item
    return best


def _is_better(item1, item2, tie_break: List[str], origin_priority: List[str], length_pref: Optional[str], entity_priority: List[str]) -> bool:
    """アイテム1がアイテム2より優れているか判定"""
    for criterion in tie_break:
        if criterion == "origin":
            origin1 = item1.get("origin", "")
            origin2 = item2.get("origin", "")
            pri1 = origin_priority.index(origin1) if origin1 in origin_priority else len(origin_priority)
            pri2 = origin_priority.index(origin2) if origin2 in origin_priority else len(origin_priority)
            if pri1 != pri2:
                return pri1 < pri2
        elif criterion == "length":
            len1 = len(item1.get("word", ""))
            len2 = len(item2.get("word", ""))
            if len1 != len2:
                return len1 > len2 if length_pref == "long" else len1 < len2
        elif criterion == "entity":
            ent1 = item1.get("entity", "")
            ent2 = item2.get("entity", "")
            pri1 = entity_priority.index(ent1) if ent1 in entity_priority else len(entity_priority)
            pri2 = entity_priority.index(ent2) if ent2 in entity_priority else len(entity_priority)
            if pri1 != pri2:
                return pri1 < pri2
    return False


@click.command(help="検出結果の重複を処理して正規化し統一スキーマでファイル出力")
@click.option("--entity-order", type=str, default="PERSON,LOCATION,DATE_TIME,PHONE_NUMBER,INDIVIDUAL_NUMBER,YEAR,PROPER_NOUN,OTHER", show_default=True, help="エンティティ優先順（カンマ区切り）")
@click.option("-j", "--json", "json_file", type=str, required=True, help="入力detect JSONファイル（必須。標準入力は不可）")
@click.option("--length-pref", type=click.Choice(["long", "short"]), default="long", show_default=True, help="長短の優先: long/short")
@click.option("--origin-priority", type=str, default="manual,custom,auto", show_default=True, help="検出由来の優先順（カンマ区切り）")
@click.option("--out", type=str, required=True, help="出力先（必須。標準出力は不可）")
@click.option("--overlap", type=click.Choice(["exact", "contain", "overlap"]), default="overlap", show_default=True, help="重複の定義: exact/contain/overlap")
@click.option("--entity-overlap-mode", type=click.Choice(["same", "any"]), default="same", show_default=True, help="エンティティ種類を考慮した重複処理: same(同じエンティティのみ), any(異なるエンティティでも重複処理)")
@click.option("--position-pref", type=click.Choice(["first", "last"]), default="first", show_default=True, help="位置の優先: first/last（入力順ベース）")
@click.option("--pretty", is_flag=True, default=False, help="JSON整形出力")
@click.option("--tie-break", "tie_break", type=str, default="origin,length,position,entity", show_default=True, help="タイブレーク順（カンマ区切り）: origin,length,entity,position の並びで指定")
@click.option("--validate", is_flag=True, default=False, help="入力JSONの検証を実施")
def main(
    entity_order: Optional[str],
    json_file: Optional[str],
    length_pref: Optional[str],
    origin_priority: Optional[str],
    out: Optional[str],
    overlap: str,
    entity_overlap_mode: str,
    position_pref: Optional[str],
    pretty: bool,
    tie_break: Optional[str],
    validate: bool,
):
    # ファイル存在確認
    if json_file:
        validate_input_file_exists(json_file)
    if out:
        validate_output_parent_exists(out)
        
    # 入力JSONはファイル必須
    raw = Path(json_file).read_text(encoding="utf-8")
    data = json.loads(raw)

    # CLI引数をそのまま使用
    tb = [s.strip() for s in (tie_break or "").split(",") if s.strip()]
    origin_pri = [s.strip().lower() for s in (origin_priority or "").split(",") if s.strip()]
    length_pref_f = length_pref
    position_pref_f = position_pref
    ent_order = [p.strip() for p in (entity_order or ",".join(conf_entity_order)).split(",") if p.strip()]
    
    # エンティティ順序の検証
    for entity in ent_order:
        if entity not in ALLOWED_ENTITY_NAMES:
            allowed_list = ", ".join(ALLOWED_ENTITY_NAMES)
            raise click.ClickException(f"未定義のエンティティ種別です: {entity}。許可されたエンティティ: {allowed_list}")

    # 仕様書形式: detectはフラット配列
    detect_list = data.get("detect", [])
    if not isinstance(detect_list, list):
        detect_list = []

    # エンティティ種類を考慮した重複処理
    result = _dedupe_detections_spec_format(
        detect_list,
        overlap=overlap,
        entity_overlap_mode=entity_overlap_mode,
        entity_priority=ent_order,
        tie_break=tb,
        origin_priority=origin_pri,
        length_pref=length_pref_f,
        position_pref=position_pref_f,
    )
    
    # 座標マップの継承
    out_obj = {
        "metadata": data.get("metadata", {}),
        "detect": result,
    }
    
    if "offset2coordsMap" in data:
        out_obj["offset2coordsMap"] = data["offset2coordsMap"]
    if "coords2offsetMap" in data:
        out_obj["coords2offsetMap"] = data["coords2offsetMap"]
        
    dump_json(out_obj, out, pretty)


if __name__ == "__main__":
    main()
