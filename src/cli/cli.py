#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyMuPDF版 PDF個人情報検出・マスキングツール - コマンドラインインターフェース

変更点:
  - バックアップPDF出力を廃止（CLI出力からも削除）
  - --export-mode で出力形式を制御（既定=1）
      1 / highlight_pdf: ハイライト済みPDFを出力（従来動作）
      2 / pdf_pii_coords: 座標情報を含むJSONを出力
      3 / text_pii_offsets: オフセット情報のJSONを出力
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import fitz  # PyMuPDF

from core.config_manager import ConfigManager
from pdf.pdf_locator import PDFTextLocator
from pdf.pdf_processor import PDFProcessor


def _collect_pdfs(path: str, recursive: bool = True) -> List[str]:
    """PDFファイルを収集する"""
    p = Path(path)
    if p.is_file():
        return [str(p)] if p.suffix.lower() == ".pdf" else []
    if p.is_dir():
        pattern = "**/*.pdf" if recursive else "*.pdf"
        return [str(pp) for pp in p.glob(pattern)]
    return []


def _dump_json(obj: Any, out_path: Optional[str], pretty: bool):
    """JSONを出力する"""
    text = json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None)
    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        click.echo(text)


def _export_pdf_pii_coords(processor: PDFProcessor, config_manager: ConfigManager, path: str, out_path: Optional[str], pretty: bool):
    """座標情報を含むJSONを出力する処理"""
    pdf_files = _collect_pdfs(path)
    results = []
    
    for pdf_path in pdf_files:
        try:
            entities = processor.analyze_pdf(pdf_path)
            file_result = {
                "file_path": pdf_path,
                "entities": []
            }
            
            for entity in entities:
                entity_data = {
                    "entity_type": entity["entity_type"],
                    "text": entity["text"],
                    "start": entity["start"],
                    "end": entity["end"],
                    "confidence": entity.get("confidence", 0.0),
                    "coordinates": entity.get("coordinates", {}),
                    "line_rects": entity.get("line_rects", [])
                }
                file_result["entities"].append(entity_data)
            
            results.append(file_result)
        except Exception as e:
            results.append({
                "file_path": pdf_path,
                "error": str(e)
            })
    
    output_data = {
        "export_mode": "pdf_pii_coords",
        "files": results
    }
    
    _dump_json(output_data, out_path, pretty)


def _export_text_pii_offsets(processor: PDFProcessor, config_manager: ConfigManager, path: str, out_path: Optional[str], pretty: bool, text_variant: str, include_text: bool):
    """オフセット情報を含むJSONを出力する処理"""
    pdf_files = _collect_pdfs(path)
    results = []
    
    for pdf_path in pdf_files:
        try:
            doc = fitz.open(pdf_path)
            locator = PDFTextLocator(doc)
            
            # テキスト抽出の基準を選択
            if text_variant == "with_newlines":
                full_text = locator.full_text_with_newlines
            else:
                full_text = locator.full_text_no_newlines
            
            enabled_entities = config_manager.get_enabled_entities()
            entities = processor.analyzer.analyze_text(full_text, enabled_entities)
            
            file_result = {
                "file_path": pdf_path,
                "text_variant": text_variant,
                "entities": []
            }
            
            if include_text:
                file_result["full_text"] = full_text
            
            for entity in entities:
                entity_data = {
                    "entity_type": entity["entity_type"],
                    "text": entity["text"],
                    "start": entity["start"],
                    "end": entity["end"],
                    "confidence": entity.get("confidence", 0.0)
                }
                file_result["entities"].append(entity_data)
            
            results.append(file_result)
            doc.close()
        except Exception as e:
            results.append({
                "file_path": pdf_path,
                "error": str(e)
            })
    
    output_data = {
        "export_mode": "text_pii_offsets",
        "files": results
    }
    
    _dump_json(output_data, out_path, pretty)


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
@click.option(
    "--export-mode",
    "-E",
    type=click.Choice(["1", "2", "3", "highlight_pdf", "pdf_pii_coords", "text_pii_offsets"]),
    default="1",
    show_default=True,
    help="出力形式: 1/highlight_pdf=ハイライトPDF, 2/pdf_pii_coords=座標JSON, 3/text_pii_offsets=オフセットJSON",
)
@click.option("--json-out", "-J", type=click.Path(), help="JSONの出力先（省略時は標準出力）")
@click.option("--pretty", is_flag=True, help="JSONを整形して出力")
@click.option(
    "--text-variant",
    type=click.Choice(["no_newlines", "with_newlines"]),
    default="no_newlines",
    show_default=True,
    help="③(text_pii_offsets)でのテキスト抽出の基準（既定: 改行なし）",
)
@click.option("--include-text", is_flag=True, help="③で抽出テキスト自体もJSONに含める")
@click.option("--exclude", multiple=True, help="除外ワード(部分一致)")
@click.option("--exclude-re", multiple=True, help="除外ワード(正規表現)")
@click.option("--person-word", multiple=True,
              help="人名として強制扱いする語を追加。複数可")
@click.option("--person-pattern", multiple=True,
              help="人名として扱う正規表現を追加。複数可")
@click.option("--person-use-auto/--no-person-use-auto", default=True,
              help="既存の自動認識と併用するか")
@click.option("--custom-names", type=str,
              help="custom_names をJSONで直接渡す。指定時は他の人名オプションより優先")
def main(path, **kwargs):
    """PyMuPDF版 PDF個人情報検出・マスキング・読み取り・復元ツール
    
    PATH: 処理するPDFファイルまたはフォルダのパス
    """
    args_dict = {k: v for k, v in kwargs.items() if v is not None}
    args_dict["pdf_masking_method"] = args_dict.pop("masking_method", None)

    # 除外設定を反映 (clickのmultiple=Trueはタプルを返す)
    if args_dict.get("exclude") or args_dict.get("exclude_re"):
        exclusions = {}
        if args_dict.get("exclude"):
            exclusions["text_exclusions"] = list(args_dict["exclude"])
        if args_dict.get("exclude_re"):
            exclusions["text_exclusions_regex"] = list(args_dict["exclude_re"])
        args_dict["exclusions"] = exclusions

    # 追加: 強制PERSONの組み立て
    # JSON直渡しがあればそれを使う
    if args_dict.get("custom_names"):
        cn = args_dict["custom_names"]
        if isinstance(cn, str):
            import json as _json
            try:
                cn = _json.loads(cn)
            except Exception:
                raise click.BadParameter("--custom-names は有効なJSONで指定してください")
        args_dict["custom_names"] = cn
    else:
        words = list(args_dict.pop("person_word", []))
        pats  = list(args_dict.pop("person_pattern", []))
        use_auto = args_dict.pop("person_use_auto", True)
        if words or pats:
            name_patterns = [
                {"name": f"cli_person_{i+1}", "regex": p, "score": 0.9}
                for i, p in enumerate(pats)
            ]
            args_dict["custom_names"] = {
                "enabled": True,
                "use_with_auto_detection": use_auto,
                "name_list": words,
                "name_patterns": name_patterns,
            }

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
            # 出力形式を解釈（デフォルト=1=ハイライトPDF）
            export_mode = args_dict.get("export_mode", "1")
            if export_mode in ("1", "highlight_pdf"):
                click.echo("\n=== PyMuPDF PDF処理結果（ハイライトPDF） ===")
                results = processor.process_files(path, args_dict.get("pdf_masking_method"))
                display_masking_results(results, config_manager)
                return
            elif export_mode in ("2", "pdf_pii_coords"):
                _export_pdf_pii_coords(
                    processor, config_manager, path, 
                    args_dict.get("json_out"), 
                    bool(args_dict.get("pretty", False))
                )
                return
            elif export_mode in ("3", "text_pii_offsets"):
                _export_text_pii_offsets(
                    processor, config_manager, path,
                    args_dict.get("json_out"),
                    bool(args_dict.get("pretty", False)),
                    args_dict.get("text_variant", "no_newlines"),
                    bool(args_dict.get("include_text", False)),
                )
                return

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
            # バックアップ出力は廃止したため表示しない
            click.echo(f"   検出数: {result['total_entities_found']}")
            if result["entities_by_type"]:
                for entity_type, count in result["entities_by_type"].items():
                    click.echo(f"     {entity_type}: {count}件")


if __name__ == "__main__":
    main()
