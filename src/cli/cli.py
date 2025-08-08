#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyMuPDF版 PDF個人情報検出・マスキングツール - コマンドラインインターフェース
"""
import logging
import click
from core.config_manager import ConfigManager
from pdf.pdf_processor import PDFProcessor


@click.command()
@click.argument("path", type=click.Path(exists=True), required=True)
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="YAML設定ファイルのパス"
)
@click.option("--verbose", "-v", is_flag=True, help="詳細なログを表示")
@click.option("--output-dir", "-o", type=click.Path(), help="出力ディレクトリ")
@click.option(
    "--read-mode",
    "-r",
    is_flag=True,
    help="読み取りモード: 既存の注釈・ハイライトを読み取り",
)
@click.option(
    "--read-report/--no-read-report",
    default=True,
    help="読み取りレポートを生成 (デフォルト: True)",
)
@click.option(
    "--restore-mode",
    is_flag=True,
    help="復元モード: レポートからPDFの注釈・ハイライトを復元",
)
@click.option(
    "--report-file",
    type=click.Path(exists=True),
    help="復元に使用するレポートファイルのパス",
)
@click.option(
    "--masking-method",
    type=click.Choice(["annotation", "highlight", "both"]),
    help="マスキング方式",
)
@click.option(
    "--masking-text-mode",
    type=click.Choice(["silent", "minimal", "verbose"]),
    help="マスキング文字表示モード",
)
@click.option(
    "--operation-mode",
    type=click.Choice(["clear_all", "append", "reset_and_append"]),
    help="操作モード",
)
@click.option("--spacy-model", "-m", type=str, help="使用するspaCyモデル名")
@click.option(
    "--deduplication-mode",
    type=click.Choice(["wider_range", "narrower_range", "entity_type"]),
    help="重複除去モード",
)
@click.option(
    "--deduplication-overlap-mode",
    type=click.Choice(["contain_only", "partial_overlap"]),
    help="重複判定モード",
)
def main(path, **kwargs):
    """
    PyMuPDF版 PDF個人情報検出・マスキング・読み取り・復元ツール

    PATH: 処理するPDFファイルまたはフォルダのパス
    """
    args_dict = {k: v for k, v in kwargs.items() if v is not None}
    args_dict["pdf_masking_method"] = args_dict.pop(
        "masking_method", None
    )  # key rename

    config_manager = ConfigManager(config_file=args_dict.get("config"), args=args_dict)

    if config_manager._safe_get_config(
        "features.logging.level"
    ) == "DEBUG" or args_dict.get("verbose"):
        logging.getLogger().setLevel(logging.DEBUG)

    processor = PDFProcessor(config_manager)

    try:
        if args_dict.get("restore_mode"):
            if not args_dict.get("report_file"):
                click.echo("エラー: 復元モードでは --report-file オプションが必要です")
                return

            click.echo("\n=== PDF復元モード ===")
            click.echo(f"復元対象: {path}")
            click.echo(f"レポートファイル: {args_dict['report_file']}")

            import fitz

            doc = fitz.open(path)
            # A new output path is needed, or we modify in place.
            output_path = processor.masker._generate_output_path(
                path
            )  # Use masker's helper
            processor.annotator.restore_pdf_from_report(doc, args_dict["report_file"])
            doc.save(output_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            doc.close()
            click.echo(f"\n復元成功: {output_path}")

        elif config_manager.is_read_mode_enabled():
            click.echo("\n=== PDF注釈読み取り結果 ===")
            results = processor.process_files(path)
            display_read_results(results)

        else:
            click.echo("\n=== PyMuPDF PDF処理結果 ===")
            results = processor.process_files(path, args_dict.get("pdf_masking_method"))
            display_masking_results(results, config_manager)

    except Exception as e:
        logging.error(f"処理中にエラーが発生しました: {e}", exc_info=True)
        click.echo(f"エラー: {e}")


def display_read_results(results):
    """読み取りモードの結果を表示"""
    if not results:
        click.echo("処理対象のファイルが見つかりませんでした。")
        return

    total_annotations = sum(
        r.get("total_annotations", 0) for r in results if "error" not in r
    )
    click.echo(f"読み取った注釈総数: {total_annotations}")

    for result in results:
        if "error" in result:
            click.echo(f"\n❌ エラー: {result['input_file']}\n   {result['error']}")
        elif "skipped" in result:
            click.echo(
                f"\n[スキップ] {result['input_file']} - 理由: {result.get('reason', '不明')}"
            )
        else:
            click.echo(f"\n[読み取り成功] {result['input_file']}")
            click.echo(f"   注釈数: {result['total_annotations']}")
            if result.get("report_file"):
                click.echo(f"   レポート: {result['report_file']}")


def display_masking_results(results, config_manager):
    """マスキングモードの結果を表示"""
    if not results:
        click.echo("処理対象のファイルが見つかりませんでした。")
        return

    total_entities = sum(
        r.get("total_entities_found", 0) for r in results if "error" not in r
    )
    click.echo(f"検出された個人情報総数: {total_entities}")
    click.echo(f"検出対象: {', '.join(config_manager.get_enabled_entities())}")
    click.echo(f"マスキング方式: {config_manager.get_pdf_masking_method()}")

    for result in results:
        if "error" in result:
            click.echo(f"\n❌ エラー: {result['input_file']}\n   {result['error']}")
        elif "skipped" in result:
            click.echo(
                f"\n[スキップ] {result['input_file']} - 理由: {result.get('reason', '不明')}"
            )
        else:
            click.echo(f"\n[成功] {result['input_file']}")
            click.echo(f"   出力: {result['output_file']}")
            if result.get("backup_file"):
                click.echo(f"   バックアップ: {result['backup_file']}")
            click.echo(f"   検出数: {result['total_entities_found']}")
            if result["entities_by_type"]:
                for entity_type, count in result["entities_by_type"].items():
                    click.echo(f"     {entity_type}: {count}件")


if __name__ == "__main__":
    main()
