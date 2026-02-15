#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import click

from src.cli.common import dump_json, validate_input_file_exists, validate_output_parent_exists
from src.core.entity_types import ENTITY_TYPES, normalize_entity_key


# entity_types.py の定義を使用
ALLOWED_ENTITY_NAMES = ENTITY_TYPES

FALLBACK_PAGE_BASE = 10 ** 15
FALLBACK_BLOCK_BASE = 10 ** 9


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_manual_entity(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("manual") is True:
        return True
    return str(item.get("origin", "")).strip().lower() == "manual"


def _normalize_origin(item: Dict[str, Any]) -> str:
    if _is_manual_entity(item):
        return "manual"

    origin = str(item.get("origin", "")).strip().lower()
    if origin == "addition":
        return "custom"
    if origin in ("manual", "custom", "auto"):
        return origin
    return "auto"


def _build_block_start_map(text_2d: Optional[List[List[str]]]) -> Dict[Tuple[int, int], int]:
    """(page_num, block_num) -> グローバル開始オフセット"""
    starts: Dict[Tuple[int, int], int] = {}
    cursor = 0
    if not isinstance(text_2d, list):
        return starts

    for page_num, page_blocks in enumerate(text_2d):
        if not isinstance(page_blocks, list):
            continue
        for block_num, block_text in enumerate(page_blocks):
            starts[(page_num, block_num)] = cursor
            cursor += len(str(block_text or ""))
    return starts


def _position_to_global(
    pos: Dict[str, Any],
    block_start_map: Dict[Tuple[int, int], int],
) -> int:
    """page/block/offset 形式を比較可能なグローバル値へ変換"""
    if not isinstance(pos, dict):
        return 0

    page_num = _safe_int(pos.get("page_num", 0))
    block_num = _safe_int(pos.get("block_num", 0))
    offset = max(0, _safe_int(pos.get("offset", 0)))

    block_start = block_start_map.get((page_num, block_num))
    if block_start is not None:
        return block_start + offset

    # text_2d上に存在しない座標（手動図形など）は疑似値で順序のみ保証
    return (
        page_num * FALLBACK_PAGE_BASE
        + block_num * FALLBACK_BLOCK_BASE
        + offset
    )


def _entity_span(
    item: Dict[str, Any],
    block_start_map: Dict[Tuple[int, int], int],
) -> Tuple[int, int]:
    start_pos = item.get("start", {})
    end_pos = item.get("end", {})
    s = _position_to_global(start_pos, block_start_map)
    e = _position_to_global(end_pos, block_start_map)
    if e < s:
        s, e = e, s
    return s, e


def _span_contains(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    return a[0] <= b[0] and b[1] <= a[1]


def _should_compare_entities(
    left: Dict[str, Any],
    right: Dict[str, Any],
    entity_overlap_mode: str,
) -> bool:
    """same モード時のエンティティ比較可否を判定"""
    if entity_overlap_mode != "same":
        return True

    left_entity = str(left.get("entity", "")).strip().upper()
    right_entity = str(right.get("entity", "")).strip().upper()
    if left_entity == right_entity:
        return True

    # PROPER_NOUN は汎用候補として他エンティティとの比較候補に含める
    # （最終的に包含関係がある場合のみ重複として採用）
    return "PROPER_NOUN" in {left_entity, right_entity}


def _dedupe_detections_spec_format(
    detect_list: List,
    overlap: str,
    entity_overlap_mode: str,
    entity_priority: List[str],
    tie_break: List[str],
    origin_priority: List[str],
    length_pref: Optional[str],
    position_pref: Optional[str],
    text_2d: Optional[List[List[str]]] = None,
) -> List:
    """仕様書形式の重複処理実装"""
    if not detect_list:
        return []

    block_start_map = _build_block_start_map(text_2d)
    n = len(detect_list)

    # 重複グラフを構築
    adjacency: List[List[int]] = [[] for _ in range(n)]
    for i in range(n):
        left = detect_list[i]
        for j in range(i + 1, n):
            right = detect_list[j]

            if not _should_compare_entities(left, right, entity_overlap_mode):
                continue

            if _positions_overlap(left, right, overlap, block_start_map):
                # sameモードの異種エンティティ比較は、包含関係がある場合のみ重複扱い
                if entity_overlap_mode == "same":
                    left_entity = str(left.get("entity", "")).strip().upper()
                    right_entity = str(right.get("entity", "")).strip().upper()
                    if left_entity != right_entity:
                        left_span = _entity_span(left, block_start_map)
                        right_span = _entity_span(right, block_start_map)
                        if not (
                            _span_contains(left_span, right_span)
                            or _span_contains(right_span, left_span)
                        ):
                            continue
                adjacency[i].append(j)
                adjacency[j].append(i)

    # 連結成分ごとに代表1件を選択
    groups: List[List[int]] = []
    visited = [False] * n
    for i in range(n):
        if visited[i]:
            continue
        stack = [i]
        visited[i] = True
        group = []
        while stack:
            current = stack.pop()
            group.append(current)
            for nxt in adjacency[current]:
                if not visited[nxt]:
                    visited[nxt] = True
                    stack.append(nxt)
        groups.append(sorted(group))

    groups.sort(key=lambda idxs: idxs[0] if idxs else 10 ** 12)

    result = []
    for group in groups:
        items = [detect_list[idx] for idx in group]
        best_item = _select_best_item(
            items,
            tie_break=tie_break,
            origin_priority=origin_priority,
            length_pref=length_pref,
            position_pref=position_pref,
            entity_priority=entity_priority,
            block_start_map=block_start_map,
        )
        result.append(best_item)

    return result

def _positions_overlap(
    item1: Dict[str, Any],
    item2: Dict[str, Any],
    overlap_mode: str,
    block_start_map: Dict[Tuple[int, int], int],
) -> bool:
    """位置の重複判定（start/endは包含端として扱う）"""
    span1 = _entity_span(item1, block_start_map)
    span2 = _entity_span(item2, block_start_map)

    if overlap_mode == "exact":
        return span1 == span2
    if overlap_mode == "contain":
        return _span_contains(span1, span2) or _span_contains(span2, span1)

    # overlap: 1文字でも交差していれば重複
    return max(span1[0], span2[0]) <= min(span1[1], span2[1])


def _select_best_item(
    items: List[Dict[str, Any]],
    tie_break: List[str],
    origin_priority: List[str],
    length_pref: Optional[str],
    position_pref: Optional[str],
    entity_priority: List[str],
    block_start_map: Dict[Tuple[int, int], int],
) -> Dict[str, Any]:
    """重複グループから最適アイテムを選択"""
    if len(items) == 1:
        return items[0]

    criteria = [c.strip().lower() for c in tie_break if str(c).strip()]
    if not criteria:
        criteria = ["origin", "contain", "length", "position", "entity"]

    normalized_origin_priority = [
        str(o).strip().lower()
        for o in origin_priority
        if str(o).strip()
    ]
    if not normalized_origin_priority:
        normalized_origin_priority = ["manual", "custom", "auto"]
    for origin in ["manual", "custom", "auto"]:
        if origin not in normalized_origin_priority:
            normalized_origin_priority.append(origin)

    origin_rank = {
        name: idx for idx, name in enumerate(normalized_origin_priority)
    }
    entity_rank = {
        str(name).upper(): idx for idx, name in enumerate(entity_priority)
    }

    spans = [_entity_span(item, block_start_map) for item in items]
    contain_metrics: List[Tuple[int, int]] = []
    for i, span in enumerate(spans):
        contains_count = 0
        contained_by_count = 0
        for j, other_span in enumerate(spans):
            if i == j:
                continue
            if _span_contains(span, other_span):
                contains_count += 1
            if _span_contains(other_span, span):
                contained_by_count += 1
        contain_metrics.append((contains_count, contained_by_count))

    prefer_short = str(length_pref or "long").strip().lower() == "short"
    prefer_last = str(position_pref or "first").strip().lower() == "last"

    def score(index: int) -> Tuple[Any, ...]:
        item = items[index]
        span_start, span_end = spans[index]
        span_len = max(0, span_end - span_start + 1)
        contains_count, contained_by_count = contain_metrics[index]
        entity_name = str(item.get("entity", "")).upper()

        keys: List[Any] = []
        for criterion in criteria:
            if criterion == "origin":
                keys.append(origin_rank.get(_normalize_origin(item), len(origin_rank)))
            elif criterion == "contain":
                # 「完全包含」優先: より多く包含し、より包含されないものを優先
                keys.append(-contains_count)
                keys.append(contained_by_count)
            elif criterion == "length":
                keys.append(span_len if prefer_short else -span_len)
            elif criterion == "position":
                keys.append(-span_start if prefer_last else span_start)
            elif criterion == "entity":
                keys.append(entity_rank.get(entity_name, len(entity_rank)))

        # 最終的には入力順で安定化
        keys.append(index)
        return tuple(keys)

    best_index = min(range(len(items)), key=score)
    return items[best_index]


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
@click.option("--tie-break", "tie_break", type=str, default="origin,contain,length,position,entity", show_default=True, help="タイブレーク順（カンマ区切り）: origin,contain,length,position,entity の並びで指定")
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
    ent_order_raw = [p.strip() for p in (entity_order).split(",") if p.strip()]

    # エンティティ順序（大文字小文字非依存、ADDRESSはLOCATIONに正規化）
    ent_order: List[str] = []
    for tok in ent_order_raw:
        normalized = normalize_entity_key(tok)
        if normalized in ALLOWED_ENTITY_NAMES:
            ent_order.append(normalized)
            continue
        allowed_list = ", ".join(ALLOWED_ENTITY_NAMES + ["ADDRESS(=LOCATION)"])
        raise click.ClickException(f"未定義のエンティティ種別です: {tok}。許可されたエンティティ: {allowed_list}")

    # 仕様書形式: detectはフラット配列
    detect_list = data.get("detect", [])
    if not isinstance(detect_list, list):
        detect_list = []
    text_2d = data.get("text", [])
    if not isinstance(text_2d, list):
        text_2d = []

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
        text_2d=text_2d,
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
