#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sys

import click

from src.core.config_manager import ConfigManager
from src.core.entity_types import ENTITY_ALIASES, ENTITY_TYPES, normalize_entity_key
from src.cli.common import dump_json, sha256_bytes, sha256_file, validate_input_file_exists, validate_output_parent_exists, validate_mutual_exclusion


# entity_types.py の定義を使用
ALLOWED_ENTITIES = ENTITY_ALIASES
ALLOWED_ENTITY_NAMES = ENTITY_TYPES

def _convert_offsets_to_position(start_offset: int, end_offset_exclusive: int, text_2d: List[List[str]]) -> Tuple[Dict[str, int], Dict[str, int]]:
    """グローバルオフセットをpage_num,block_num,offset形式に変換

    注意:
    - start_offset は最初の文字の位置（0-based）
    - end_offset_exclusive はPythonスライス互換の終端（非包含）
    - 本関数は end.offset を「最後の文字そのもの」の位置（包含）に合わせて算出する
    - 開始と終了は別々のブロック/ページにまたがってもよい
    """

    # 終了位置は包含端に合わせる（最後の文字そのもののオフセット）
    last_char_global = max(0, end_offset_exclusive - 1)

    start_pos: Optional[Dict[str, int]] = None
    end_pos: Optional[Dict[str, int]] = None

    current_offset = 0
    last_page_num = 0
    last_block_num = 0
    last_block_len = 0

    for page_num, page_blocks in enumerate(text_2d):
        for block_num, block_text in enumerate(page_blocks):
            block_len = len(block_text)
            last_page_num = page_num
            last_block_num = block_num
            last_block_len = block_len

            # start の属する位置
            if start_pos is None and current_offset <= start_offset < current_offset + block_len:
                start_pos = {
                    "page_num": page_num,
                    "block_num": block_num,
                    "offset": start_offset - current_offset,
                }

            # end(包含) の属する位置
            if end_pos is None and current_offset <= last_char_global < current_offset + block_len:
                end_pos = {
                    "page_num": page_num,
                    "block_num": block_num,
                    "offset": last_char_global - current_offset,
                }

            current_offset += block_len

    # フォールバック: いずれか見つからない場合、末尾/先頭にクランプ
    if start_pos is None:
        start_pos = {"page_num": 0, "block_num": 0, "offset": 0}
    if end_pos is None:
        # 最後のブロックの末尾に合わせる（空でない前提。空なら0にクランプ）
        end_pos = {
            "page_num": last_page_num,
            "block_num": last_block_num,
            "offset": max(0, last_block_len - 1),
        }
    return start_pos, end_pos


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


@click.command(help="read出力(JSON)からPIIを検出し統一スキーマでファイル出力")
@click.option("--add", "adds", multiple=True, help="追加エンティティ: --add <entity>:<regex>（複数可）")
@click.option("--exclude", "excludes", multiple=True, help="全エンティティ共通の除外正規表現（複数可）")
@click.option("-j", "--json", "json_file", type=str, required=True, help="入力read JSONファイル（必須。標準入力は不可）")
@click.option("--model", multiple=True, default=["ja_core_news_trf"], show_default=True, help="spaCyモデルID（複数可。高精度: ja_core_news_trf, ja_ginza_electra）")
@click.option("--out", type=str, required=True, help="出力先（必須。標準出力は不可）")
@click.option("--pretty", is_flag=True, default=False, help="JSON整形出力")
@click.option("--validate", is_flag=True, default=False, help="入力JSONのスキーマ検証を実施")
@click.option("--with-predetect/--no-predetect", default=True, help="入力のdetect情報を含める（旧--highlights-merge append相当）")
@click.option("--entity", "entities_csv", type=str, help="検出するエンティティ（CSV例: 'PERSON,ADDRESS'。未指定=全エンティティ）")
def main(adds: Tuple[str, ...], excludes: Tuple[str, ...], json_file: Optional[str], model: Tuple[str, ...], out: Optional[str], pretty: bool, validate: bool, with_predetect: bool, entities_csv: Optional[str]):
    # ファイル存在確認
    if json_file:
        validate_input_file_exists(json_file)
    if out:
        validate_output_parent_exists(out)
    
    # 入力JSONはファイル必須
    data_txt = Path(json_file).read_text(encoding="utf-8")
    try:
        data = json.loads(data_txt)
    except Exception as e:
        raise click.ClickException(f"入力JSONの読み込みに失敗: {e}")

    # 簡易検証（新スキーマ）
    meta = data.get("metadata", {}) or {}
    pdf_path = (meta.get("pdf", {}) or {}).get("path")
    if not pdf_path or not Path(pdf_path).exists():
        raise click.ClickException("metadata.pdf.path にPDFの絶対パスが必要です（readの出力を使用してください）")

    # 仕様書に従い、textフィールドから2D配列形式のデータを取得
    text_2d = data.get("text", [])
    plain_text = None
    if isinstance(text_2d, list) and text_2d:
        try:
            # 2D配列の全ブロックを順序通りにフラット結合（区切りは入れない）
            # 改行/改ブロック/改ページに跨るPIIも検出できるよう、文字列を一度フラット化する
            full_plain_text_parts = []
            for page_blocks in text_2d:
                if isinstance(page_blocks, list):
                    for block in page_blocks:
                        full_plain_text_parts.append(str(block))
            plain_text = "".join(full_plain_text_parts)
        except Exception:
            plain_text = None

    cfg = ConfigManager()
    from src.analysis.analyzer import Analyzer  # Lazy heavy dep

    analyzer = Analyzer(cfg)

    detections_plain: List[Dict[str, Any]] = []

    import fitz  # Lazy import
    from src.pdf.pdf_locator import PDFTextLocator

    with fitz.open(pdf_path) as doc:
        locator = PDFTextLocator(doc)
        target_text = plain_text if isinstance(plain_text, str) else locator.full_text_no_newlines
        # --entity 指定の解釈（CSV）。ADDRESSはLOCATIONのエイリアス。
        selected_entities: Optional[List[str]] = None
        if entities_csv:
            tokens = [t.strip() for t in str(entities_csv).split(',') if t.strip()]
            selected_entities = []
            for tok in tokens:
                t_low = tok.lower()
                if t_low == 'address':
                    selected_entities.append('LOCATION')
                    continue
                if t_low in ALLOWED_ENTITIES:
                    selected_entities.append(ALLOWED_ENTITIES[t_low])
                    continue
                t_up = tok.upper()
                if t_up in ALLOWED_ENTITY_NAMES:
                    selected_entities.append(t_up)
                    continue
                allowed_aliases = sorted(list(ALLOWED_ENTITIES.keys()) + ["address"])
                raise click.ClickException(f"未定義のエンティティです: {tok}. 許可: {', '.join(allowed_aliases)} または {', '.join(ALLOWED_ENTITY_NAMES)}")
        # モデル検出に用いるエンティティ集合（未指定は全エンティティ＝ConfigManager側で全有効）
        model_entities = selected_entities if selected_entities else cfg.get_enabled_entities()
        model_results = analyzer.analyze_text(target_text, model_entities)

        # 引数 --add / --exclude をパース
        def parse_add_arg(s: str) -> Tuple[str, str]:
            if ":" not in s:
                raise click.ClickException("--add は <entity>:<regex> 形式で指定してください")
            ent_name, regex = s.split(":", 1)
            ent_key = ent_name.strip().lower()
            if ent_key not in ALLOWED_ENTITIES:
                allowed_list = ", ".join(sorted(ALLOWED_ENTITIES.keys()))
                raise click.ClickException(f"未定義のエンティティ種別です: {ent_name}。許可されたエンティティ: {allowed_list}")
            if not regex:
                raise click.ClickException("--add の正規表現が空です")
            return ALLOWED_ENTITIES[ent_key], regex

        add_specs: List[Tuple[str, str]] = [parse_add_arg(a) for a in adds]
        exclude_specs: List[str] = list(excludes)

        for r in model_results:
            ent = r.get("entity_type") or r.get("entity")
            s = int(r["start"]); e = int(r["end"])  # codepoint offsets (no newlines)
            txt = target_text[s:e]
            did = _detection_id(ent, txt, (s, e))
            # 仕様書形式: start/endをpage_num,block_num,offset形式に変換
            # endは「最後の文字そのもの」のoffset（包含端）になるようにマッピング
            start_pos, end_pos = _convert_offsets_to_position(s, e, text_2d)
            entry_plain = {
                "start": start_pos,
                "end": end_pos,
                "entity": ent,
                "word": txt,
                "origin": "auto"
            }
            detections_plain.append(entry_plain)

        # 追加の正規表現での検出（origin: custom）
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
                # endは包含端に合わせる
                start_pos, end_pos = _convert_offsets_to_position(s, e, text_2d)
                detections_plain.append({
                    "start": start_pos,
                    "end": end_pos,
                    "entity": ent_name,
                    "word": txt,
                    "origin": "custom"
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

        # 追加 > 除外 > 自動検出: 除外は自動検出（origin=auto）のみから除去
        if exclude_spans:
            def overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
                return max(a[0], b[0]) < min(a[1], b[1])

            def is_auto(entry: Dict[str, Any]) -> bool:
                return entry.get("origin") == "auto"

            # 仕様書形式では除外処理も簡略化
            detections_plain = [
                d for d in detections_plain
                if not is_auto(d) or not any(overlaps((0, 0), es) for es in exclude_spans)  # 簡略化
            ]

    # 既存detect情報の統合
    existing_detect = data.get("detect", [])
    if with_predetect and isinstance(existing_detect, list):
        merged_detect = list(existing_detect) + detections_plain
    else:
        merged_detect = detections_plain

    # 座標マップの継承
    offset2coords_map = data.get("offset2coordsMap", {})
    coords2offset_map = data.get("coords2offsetMap", {})

    # metadataは入力を踏襲しつつ、generated_atを更新
    metadata = dict(meta)
    metadata["generated_at"] = datetime.utcnow().isoformat() + "Z"

    # 仕様書形式でJSON出力
    out_obj = {
        "metadata": metadata,
        "detect": merged_detect,
    }
    
    if offset2coords_map:
        out_obj["offset2coordsMap"] = offset2coords_map
    if coords2offset_map:
        out_obj["coords2offsetMap"] = coords2offset_map
        
    dump_json(out_obj, out, pretty)


if __name__ == "__main__":
    main()
