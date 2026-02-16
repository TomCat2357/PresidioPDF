#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import hashlib
import logging
import sys
from pathlib import Path
from typing import Any, Optional
import click

logger = logging.getLogger(__name__)


def dump_json(obj: Any, out_path: Optional[str], pretty: bool):
    text = json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None)
    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        # Print to stdout without extra formatting
        print(text)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_pdf_content(pdf_path: str) -> str:
    """PDFコンテンツハッシュ（注釈・埋め込みファイルに依存しない）"""
    import fitz
    h = hashlib.sha256()
    with fitz.open(pdf_path) as doc:
        h.update(str(doc.page_count).encode("utf-8"))
        for page in doc:
            h.update(page.get_text("text").encode("utf-8"))
            r = page.rect
            h.update(f"{r.x0:.6f},{r.y0:.6f},{r.x1:.6f},{r.y1:.6f}".encode("utf-8"))
            h.update(str(len(page.get_images())).encode("utf-8"))
    return h.hexdigest()


def validate_input_file_exists(path: str) -> None:
    """読み込み系ファイルの存在確認"""
    if not Path(path).exists():
        raise click.ClickException(f"入力ファイルが存在しません: {path}")


def validate_output_parent_exists(path: str) -> None:
    """出力系ファイルの親ディレクトリ存在確認"""
    parent = Path(path).parent
    if not parent.exists():
        raise click.ClickException(f"出力先の親ディレクトリが存在しません: {parent}")


def validate_mutual_exclusion(flag1: bool, flag2: bool, name1: str, name2: str) -> None:
    """相互排他オプションの確認"""
    if flag1 and flag2:
        raise click.ClickException(f"{name1}と{name2}は同時指定できません")


def embed_coordinate_map(original_pdf_path: str, output_pdf_path: str) -> bool:
    """座標マップを出力PDFに埋め込む

    mask_main / pdf_processor / embed_main で共通利用される処理。
    """
    try:
        from src.pdf.pdf_coordinate_mapper import PDFCoordinateMapper  # Lazy import

        mapper = PDFCoordinateMapper()

        if not mapper.load_or_create_coordinate_map(original_pdf_path):
            logger.warning(f"座標マップの生成に失敗しました: {original_pdf_path}")
            return False

        temp_path = output_pdf_path + ".temp"
        if mapper.save_pdf_with_coordinate_map(output_pdf_path, temp_path):
            Path(temp_path).replace(output_pdf_path)
            logger.info(f"座標マップを埋め込みました: {output_pdf_path}")
            return True
        else:
            logger.warning(f"座標マップの埋め込みに失敗しました: {output_pdf_path}")
            return False

    except Exception as e:
        logger.error(f"座標マップ埋め込みエラー: {e}")
        return False

