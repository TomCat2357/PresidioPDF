#!/usr/bin/env python3
"""
embed_main.py - PDF座標マップ埋め込みコマンド

PDFファイルに座標マップを埋め込む専用コマンド。
元のmask_main.pyから--embed-coordinates機能を分離。
"""

import click

from src.cli.common import (
    copy_pdf_to_output,
    embed_coordinate_map,
    load_json_file,
    option_force,
    option_json,
    option_out,
    option_pdf,
    require_coordinate_maps,
    validate_input_file_exists,
    validate_output_parent_exists,
    verify_pdf_hash,
)


@click.command(help="PDFに座標マップを埋め込む")
@option_pdf("入力PDFファイルのパス")
@option_json("座標マップを含むJSONファイル")
@option_out("出力PDFパス（指定必須）")
@option_force()
def main(pdf: str, json_file: str, out: str, force: bool):
    validate_input_file_exists(pdf)
    validate_input_file_exists(json_file)
    validate_output_parent_exists(out)

    data = load_json_file(json_file, "JSONファイル")
    require_coordinate_maps(data, json_file)
    verify_pdf_hash(
        pdf,
        data.get("metadata", {}),
        force,
        "PDFとJSONのsha256が一致しません (--force で無視)",
    )
    copy_pdf_to_output(pdf, out)

    if embed_coordinate_map(pdf, out):
        print(out)
    else:
        raise click.ClickException("座標マップの埋め込みに失敗しました")


if __name__ == "__main__":
    main()
