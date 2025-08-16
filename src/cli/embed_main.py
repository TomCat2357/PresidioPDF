#!/usr/bin/env python3
"""
embed_main.py - PDF座標マップ埋め込みコマンド

PDFファイルに座標マップを埋め込む専用コマンド。
元のmask_main.pyから--embed-coordinates機能を分離。
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click

from src.cli.common import validate_input_file_exists, validate_output_parent_exists
from src.core.config_manager import ConfigManager


def _embed_coordinate_map(original_pdf_path: str, json_file_path: str, output_pdf_path: str) -> bool:
    """座標マップをPDFに埋め込む"""
    try:
        from src.pdf.pdf_coordinate_mapper import PDFCoordinateMapper  # Lazy import
        
        # JSONファイルから座標マップを読み込み
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        offset2coords_map = data.get("offset2coordsMap", {})
        coords2offset_map = data.get("coords2offsetMap", {})
        
        if not offset2coords_map and not coords2offset_map:
            print(f"警告: JSONファイルに座標マップが含まれていません: {json_file_path}", file=sys.stderr)
            return False
        
        mapper = PDFCoordinateMapper()
        
        # 元のPDFから座標マップを生成または読み込み
        if not mapper.load_or_create_coordinate_map(original_pdf_path):
            print(f"警告: 座標マップの生成に失敗しました: {original_pdf_path}", file=sys.stderr)
            return False
        
        # 出力PDFに座標マップを埋め込み（一時ファイルを経由）
        temp_path = output_pdf_path + ".temp"
        if mapper.save_pdf_with_coordinate_map(original_pdf_path, temp_path):
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


@click.command(help="PDFに座標マップを埋め込む")
@click.option("--pdf", type=str, required=True, help="入力PDFファイルのパス")
@click.option("-j", "--json", "json_file", type=str, required=True, help="座標マップを含むJSONファイル")
@click.option("--out", type=str, required=True, help="出力PDFパス（指定必須）")
@click.option("--config", type=str, help="設定ファイル")
@click.option("--force", is_flag=True, default=False, help="ハッシュ不一致でも続行")
def main(pdf: str, json_file: str, out: str, config: Optional[str], force: bool):
    # ファイル存在確認
    validate_input_file_exists(pdf)
    validate_input_file_exists(json_file)
    if config:
        validate_input_file_exists(config)
    validate_output_parent_exists(out)
    
    cfg = ConfigManager()
    
    # JSONファイルの読み込みと検証
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # PDFハッシュの検証
    from src.cli.common import sha256_file
    
    pdf_sha = sha256_file(pdf)
    ref_sha = ((data.get("metadata", {}) or {}).get("pdf", {}) or {}).get("sha256")
    if ref_sha and ref_sha != pdf_sha and not force:
        raise click.ClickException("PDFとJSONのsha256が一致しません (--force で無視)")
    
    # 出力ディレクトリの作成
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    
    # 元のPDFを出力先にコピー
    with open(pdf, "rb") as r, open(out, "wb") as w:
        w.write(r.read())
    
    # 座標マップの埋め込み
    if _embed_coordinate_map(pdf, json_file, out):
        print(out)
    else:
        raise click.ClickException("座標マップの埋め込みに失敗しました")


if __name__ == "__main__":
    main()