#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from src.core.config_manager import ConfigManager
from src.cli.common import validate_input_file_exists, validate_output_parent_exists


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


def _embed_coordinate_map(original_pdf_path: str, output_pdf_path: str) -> bool:
    """座標マップを出力PDFに埋め込む"""
    try:
        from src.pdf.pdf_coordinate_mapper import PDFCoordinateMapper  # Lazy import
        
        mapper = PDFCoordinateMapper()
        
        # 元のPDFから座標マップを生成または読み込み
        if not mapper.load_or_create_coordinate_map(original_pdf_path):
            print(f"警告: 座標マップの生成に失敗しました: {original_pdf_path}", file=sys.stderr)
            return False
        
        # 出力PDFに座標マップを埋め込み（一時ファイルを経由）
        temp_path = output_pdf_path + ".temp"
        if mapper.save_pdf_with_coordinate_map(output_pdf_path, temp_path):
            # 一時ファイルを元のファイルに置き換え
            Path(temp_path).replace(output_pdf_path)
            print(f"座標マップを埋め込みました: {output_pdf_path}", file=sys.stderr)
            return True
        else:
            print(f"警告: 座標マップの埋め込みに失敗しました: {output_pdf_path}", file=sys.stderr)
            return False
            
    except Exception as e:
        print(f"座標マップ埋め込みエラー: {e}", file=sys.stderr)
        return False


@click.command(help="検出JSON(detect.structured)を使ってPDFにハイライト注釈を追加（入力はファイル必須）")
@click.option("--config", type=str, help="設定ファイル（maskセクションのみ参照）")
@click.option("--force", is_flag=True, default=False, help="ハッシュ不一致でも続行")
@click.option("-j", "--json", "json_file", type=str, required=True, help="入力detect JSONファイル（必須。標準入力は不可）")
@click.option("--out", type=str, required=True, help="出力PDFパス（指定必須）")
@click.option("--pdf", type=str, required=True, help="入力PDFファイルのパス")
@click.option("--validate", is_flag=True, default=False, help="検出JSONのスキーマ検証を実施")
@click.option("--embed-coordinates/--no-embed-coordinates", default=False, help="座標マップをPDFに埋め込む")
def main(config: Optional[str], force: bool, json_file: Optional[str], out: str, pdf: str, validate: bool, embed_coordinates: bool):
    # ファイル存在確認
    validate_input_file_exists(pdf)
    if json_file:
        validate_input_file_exists(json_file)
    if config:
        validate_input_file_exists(config)
    validate_output_parent_exists(out)
        
    cfg = ConfigManager()
    # 入力JSONはファイル必須
    raw = Path(json_file).read_text(encoding="utf-8")
    det = json.loads(raw)
    if validate:
        errors = _validate_detect_json(det)
        if errors:
            raise click.ClickException("detect JSON validation failed: " + "; ".join(errors))

    # Validate hash against JSON reference when present
    from src.cli.common import sha256_file

    pdf_sha = sha256_file(pdf)
    ref_sha = ((det.get("metadata", {}) or {}).get("pdf", {}) or {}).get("sha256")
    if ref_sha and ref_sha != pdf_sha and not force:
        raise click.ClickException("PDFと検出JSONのsha256が一致しません (--force で無視)")

    # Build entities from detect.structured
    entities: List[Dict[str, Any]] = []
    for st in (det.get("detect", {}) or {}).get("structured", []) or []:
        for q in st.get("quads", []) or []:
            entities.append(
                {
                    "entity_type": st.get("entity", "PII"),
                    "text": st.get("text", ""),
                    "line_rects": [
                        {
                            "rect": {"x0": float(q[0]), "y0": float(q[1]), "x1": float(q[2]), "y1": float(q[3])},
                            "page_num": max(0, int(st.get("page", 1)) - 1),
                        }
                    ],
                }
            )

    from src.pdf.pdf_masker import PDFMasker  # Lazy import

    masker = PDFMasker(cfg)
    # --outは必須なので常にファイル出力
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(pdf, "rb") as r, open(out, "wb") as w:
        w.write(r.read())
    masker._apply_highlight_masking_with_mode(out, entities, cfg.get_operation_mode())
    
    # 座標マップ埋め込み処理
    if embed_coordinates:
        _embed_coordinate_map(pdf, out)
    
    print(out)


if __name__ == "__main__":
    main()
