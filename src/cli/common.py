#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import hashlib
from pathlib import Path
from typing import Any, Optional
import click


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

