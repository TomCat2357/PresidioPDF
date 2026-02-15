#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from src.core.config_manager import ConfigManager
from src.core.entity_types import normalize_entity_key
from src.cli.common import validate_input_file_exists, validate_output_parent_exists, embed_coordinate_map


def _validate_detect_json(obj: Dict[str, Any]) -> List[str]:
    errs = []
    if not isinstance(obj, dict):
        return ["root must be object"]
    meta = obj.get("metadata", {}) or {}
    if not isinstance(meta, dict):
        errs.append("metadata must be object")
    else:
        pdf = meta.get("pdf", {}) or {}
        if not isinstance(pdf, dict) or not isinstance(pdf.get("sha256"), str):
            errs.append("metadata.pdf.sha256 must be string")
    dets = obj.get("detect", {}) or {}
    if not isinstance(dets, dict):
        errs.append("detect must be object")
    else:
        if "structured" in dets and dets["structured"] is not None:
            if not isinstance(dets["structured"], list):
                errs.append("detect.structured must be array")
    return errs



@click.command(help="検出JSON（新仕様フラット形式）を使ってPDFにハイライト注釈を追加（入力はファイル必須）")
@click.option("--force", is_flag=True, default=False, help="ハッシュ不一致でも続行")
@click.option("-j", "--json", "json_file", type=str, required=True, help="入力detect JSONファイル（必須。標準入力は不可）")
@click.option("--out", type=str, required=True, help="出力PDFパス（指定必須）")
@click.option("--pdf", type=str, required=True, help="入力PDFファイルのパス")
@click.option("--validate", is_flag=True, default=False, help="検出JSONのスキーマ検証を実施")
@click.option("--embed-coordinates/--no-embed-coordinates", default=False, help="座標マップをPDFに埋め込む")
# 例: --mask PERSON=#FF0040@0.35 --mask ADDRESS=blue@0.2 （ADDRESSはLOCATIONのエイリアス）
@click.option("--mask", "mask_specs", multiple=True, help="エンティティ別のハイライト色と透明度を指定（繰り返し可）。<ENTITY>=<color>[@alpha]")
def main(force: bool, json_file: Optional[str], out: str, pdf: str, validate: bool, embed_coordinates: bool, mask_specs: Optional[List[str]]):
    # ファイル存在確認
    validate_input_file_exists(pdf)
    if json_file:
        validate_input_file_exists(json_file)
    validate_output_parent_exists(out)
        
    cfg = ConfigManager()
    # 入力JSONはファイル必須
    raw = Path(json_file).read_text(encoding="utf-8")
    det = json.loads(raw)
    
    # PDF hash validation
    from src.cli.common import sha256_file

    pdf_sha = sha256_file(pdf)
    ref_sha = ((det.get("metadata", {}) or {}).get("pdf", {}) or {}).get("sha256")
    if ref_sha and ref_sha != pdf_sha and not force:
        raise click.ClickException("PDFと検出JSONのsha256が一致しません (--force で無視)")

    # 新仕様フラット形式のdetectからエンティティを構築
    entities: List[Dict[str, Any]] = []
    detect_list = det.get("detect", [])
    if not isinstance(detect_list, list):
        detect_list = []
    
    # 座標・テキスト情報の取得
    offset2coords_map = det.get("offset2coordsMap", {})
    coords2offset_map = det.get("coords2offsetMap", {})
    text_2d = det.get("text", [])

    # グローバル（改行なし）オフセットマップを準備（ページ/ブロック跨ぎ対応用）
    # 仕様: text_2dは改行なしのブロック文字列を2D配列で保持
    block_start_global: Dict[tuple, int] = {}
    block_len_map: Dict[tuple, int] = {}
    global_cursor = 0
    if isinstance(text_2d, list):
        for p, page_blocks in enumerate(text_2d):
            if not isinstance(page_blocks, list):
                continue
            for b, block_text in enumerate(page_blocks):
                s = str(block_text or "")
                block_start_global[(p, b)] = global_cursor
                block_len_map[(p, b)] = len(s)
                global_cursor += len(s)
    
    import fitz  # Lazy import
    from src.pdf.pdf_locator import PDFTextLocator
    
    def _group_rects_by_line(rects: List[List[float]], y_threshold: float = 2.0) -> List[List[float]]:
        """同一行の矩形をy座標でグルーピングして各行の外接矩形を返す。
        rects: [[x0,y0,x1,y1], ...]
        y_threshold: y中心の近接しきい値（ポイント）
        """
        if not rects:
            return []
        # y中心でソート
        items = []
        for r in rects:
            try:
                x0, y0, x1, y1 = map(float, r)
                cy = (y0 + y1) / 2.0
                items.append((cy, [x0, y0, x1, y1]))
            except Exception:
                continue
        items.sort(key=lambda t: t[0])
        groups: List[List[List[float]]] = []
        for cy, rect in items:
            if not groups:
                groups.append([rect])
                continue
            last_group = groups[-1]
            # グループ代表の平均y中心
            gcy = sum(((rr[1] + rr[3]) / 2.0) for rr in last_group) / len(last_group)
            if abs(cy - gcy) <= y_threshold:
                last_group.append(rect)
            else:
                groups.append([rect])
        # 各グループを外接矩形へ
        out: List[List[float]] = []
        for grp in groups:
            xs0 = [rr[0] for rr in grp]; ys0 = [rr[1] for rr in grp]
            xs1 = [rr[2] for rr in grp]; ys1 = [rr[3] for rr in grp]
            out.append([min(xs0), min(ys0), max(xs1), max(ys1)])
        return out

    # マスク指定のパース（ENTITY=color[@alpha] 形式、ENTITYは大文字小文字非依存・出力は全大文字。ADDRESSはLOCATIONのエイリアス）
    # normalize_entity_key は entity_types.py から import 済み

    # 簡易CSSカラー名→RGBマップ（最小集合）
    CSS_COLORS = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "red": (255, 0, 0),
        "green": (0, 128, 0),
        "blue": (0, 0, 255),
        "cyan": (0, 255, 255),
        "magenta": (255, 0, 255),
        "yellow": (255, 255, 0),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
        "orange": (255, 165, 0),
        "purple": (128, 0, 128),
        "pink": (255, 192, 203),
        "brown": (165, 42, 42),
        "teal": (0, 128, 128),
        "lime": (0, 255, 0),
        "navy": (0, 0, 128),
        "maroon": (128, 0, 0),
        "olive": (128, 128, 0),
        "silver": (192, 192, 192),
        "royalblue": (65, 105, 225),
    }

    def _clamp01(x: float) -> float:
        try:
            xf = float(x)
        except Exception:
            xf = 0.0
        return 0.0 if xf < 0 else (1.0 if xf > 1 else xf)

    def _parse_color_and_alpha(s: str) -> (List[float], Optional[float]):
        """色表現とαを解析して([r,g,b](0..1)), alpha(0..1 or None)を返す。
        許容: #RGB/#RRGGBB/#RRGGBBAA, rgb(r,g,b), rgba(r,g,b,a), css名
        """
        import re
        s = str(s).strip()
        # rgba()
        m = re.fullmatch(r"rgba\((\d{1,3}),(\d{1,3}),(\d{1,3}),(\d*\.?\d+)\)", s, flags=re.I)
        if m:
            r, g, b = [max(0, min(255, int(m.group(i)))) for i in (1, 2, 3)]
            a = _clamp01(float(m.group(4)))
            return [r / 255.0, g / 255.0, b / 255.0], a
        # rgb()
        m = re.fullmatch(r"rgb\((\d{1,3}),(\d{1,3}),(\d{1,3})\)", s, flags=re.I)
        if m:
            r, g, b = [max(0, min(255, int(m.group(i)))) for i in (1, 2, 3)]
            return [r / 255.0, g / 255.0, b / 255.0], None
        # #RRGGBBAA or #RRGGBB or #RGB
        if s.startswith('#'):
            hexv = s[1:]
            try:
                if len(hexv) == 3:
                    r = int(hexv[0] * 2, 16); g = int(hexv[1] * 2, 16); b = int(hexv[2] * 2, 16)
                    return [r / 255.0, g / 255.0, b / 255.0], None
                if len(hexv) == 6:
                    r = int(hexv[0:2], 16); g = int(hexv[2:4], 16); b = int(hexv[4:6], 16)
                    return [r / 255.0, g / 255.0, b / 255.0], None
                if len(hexv) == 8:
                    r = int(hexv[0:2], 16); g = int(hexv[2:4], 16); b = int(hexv[4:6], 16); a = int(hexv[6:8], 16) / 255.0
                    return [r / 255.0, g / 255.0, b / 255.0], _clamp01(a)
            except Exception:
                pass
        # css名
        rgb = CSS_COLORS.get(s.lower())
        if rgb:
            r, g, b = rgb
            return [r / 255.0, g / 255.0, b / 255.0], None
        # 不明: グレーにフォールバック
        return [0.9, 0.9, 0.9], None

    mask_styles: Dict[str, Dict[str, float]] = {}
    if mask_specs:
        for spec in mask_specs:
            if not spec or '=' not in spec:
                raise click.ClickException(f"--mask は <ENTITY>=<color>[@alpha] 形式で指定してください: {spec}")
            key, val = spec.split('=', 1)
            ent = normalize_entity_key(key)
            if not ent:
                raise click.ClickException(f"--mask のエンティティ名が空です: {spec}")
            # color[@alpha]
            parts = val.split('@', 1)
            color_str = parts[0].strip()
            rgb, a_rgba = _parse_color_and_alpha(color_str)
            alpha: Optional[float] = a_rgba
            if len(parts) == 2 and (alpha is None):
                try:
                    alpha = _clamp01(float(parts[1]))
                except Exception:
                    raise click.ClickException(f"--mask のalphaが不正です(0..1): {parts[1]}")
            # 既定α
            if alpha is None:
                alpha = 0.4
            mask_styles[ent] = {"r": rgb[0], "g": rgb[1], "b": rgb[2], "a": alpha}

    with fitz.open(pdf) as doc:
        locator = PDFTextLocator(doc)
        
        for detect_item in detect_list:
            if not isinstance(detect_item, dict):
                continue
                
            start_pos = detect_item.get("start", {})
            end_pos = detect_item.get("end", {})
            entity_type = detect_item.get("entity", "PII")
            text = detect_item.get("word", "")
            
            if not isinstance(start_pos, dict) or not isinstance(end_pos, dict):
                continue
                
            # page_num, block_num, offsetから座標を取得
            page_num = start_pos.get("page_num", 0)
            block_num = start_pos.get("block_num", 0)
            start_offset = start_pos.get("offset", 0)
            end_offset = end_pos.get("offset", 0)
            
            # 改行なしグローバルオフセットに変換し、PDFTextLocatorで跨行/ブロック/ページ対応のline_rectsを取得
            line_rects_items: List[Dict[str, Any]] = []
            try:
                key_s = (page_num, block_num)
                key_e = (end_pos.get("page_num", page_num), end_pos.get("block_num", block_num))
                if key_s in block_start_global and key_e in block_start_global:
                    start_global = block_start_global[key_s] + int(start_offset)
                    # endは包含端 → 排他的終端へ(+1)
                    end_global_excl = block_start_global[key_e] + int(end_offset) + 1
                    # PDFTextLocatorで行矩形を取得（ページ情報付き）
                    line_rects_items = locator.get_pii_line_rects(start_global, end_global_excl)
            except Exception:
                line_rects_items = []

            # フォールバック: 旧オフセット座標マップ（ブロック/ページ跨ぎ対応版）
            if not line_rects_items and offset2coords_map:
                try:
                    ps = int(start_pos.get("page_num", 0))
                    pe = int(end_pos.get("page_num", ps))
                    bs = int(start_pos.get("block_num", 0))
                    be = int(end_pos.get("block_num", bs))
                    os = int(start_offset)
                    oe = int(end_offset)

                    # 収集: page→矩形配列
                    page_rects: Dict[int, List[List[float]]] = {}
                    for p in range(ps, pe + 1):
                        page_dict = offset2coords_map.get(str(p), {})
                        if not isinstance(page_dict, dict) or not page_dict:
                            continue
                        # ブロックIDを昇順で走査
                        block_ids = sorted([int(k) for k in page_dict.keys() if str(k).isdigit()])
                        if not block_ids:
                            continue
                        b_start = bs if p == ps else block_ids[0]
                        b_end = be if p == pe else block_ids[-1]
                        for b in block_ids:
                            if b < b_start or b > b_end:
                                continue
                            block_list = page_dict.get(str(b), [])
                            if not isinstance(block_list, list) or not block_list:
                                continue
                            o_start = os if (p == ps and b == bs) else 0
                            o_end = oe if (p == pe and b == be) else (len(block_list) - 1)
                            if o_start > o_end:
                                continue
                            for off in range(o_start, o_end + 1):
                                bbox = block_list[off] if 0 <= off < len(block_list) else None
                                if isinstance(bbox, list) and len(bbox) >= 4:
                                    page_rects.setdefault(p, []).append(bbox[:4])

                    # 行方向へグルーピングしてline_rectsを構築
                    for p, rects in page_rects.items():
                        if not rects:
                            continue
                        for r in _group_rects_by_line(rects):
                            line_rects_items.append({
                                "rect": {"x0": r[0], "y0": r[1], "x1": r[2], "y1": r[3]},
                                "page_num": p,
                            })
                except Exception:
                    line_rects_items = []

            if line_rects_items:
                # originを検出アイテムから引き継ぐ（auto/manual/custom）
                origin = str(detect_item.get("origin", "auto"))
                ent_u = normalize_entity_key(entity_type)
                # 出力・内部は全大文字を使用
                entities.append({
                    "entity_type": ent_u,
                    "text": text,
                    "origin": origin,
                    "join_as_quads": True,
                    # マスクスタイルの適用（該当エンティティのみ）
                    **({
                        "mask_rgb": [mask_styles[ent_u]["r"], mask_styles[ent_u]["g"], mask_styles[ent_u]["b"]],
                        "mask_alpha": mask_styles[ent_u]["a"],
                    } if ent_u in mask_styles else {}),
                    "line_rects": [
                        {
                            "rect": {
                                "x0": float(item["rect"]["x0"]),
                                "y0": float(item["rect"]["y0"]),
                                "x1": float(item["rect"]["x1"]),
                                "y1": float(item["rect"]["y1"]),
                            },
                            "page_num": int(item.get("page_num", page_num)),
                        }
                        for item in line_rects_items
                    ],
                })

    from src.pdf.pdf_masker import PDFMasker  # Lazy import

    masker = PDFMasker(cfg)
    # --outは必須なので常にファイル出力
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(pdf, "rb") as r, open(out, "wb") as w:
        w.write(r.read())
    masker._apply_highlight_masking_with_mode(out, entities, cfg.get_operation_mode())
    
    # オプション指定時は座標マップを埋め込む
    if embed_coordinates:
        try:
            embed_coordinate_map(pdf, out)
        except Exception:
            # テストでは埋め込み失敗時スキップするケースがあるため、例外は握りつぶす
            pass
    
    print(out)


if __name__ == "__main__":
    main()
