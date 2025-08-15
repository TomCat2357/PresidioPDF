#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add workspace to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import click

from src.core.config_manager import ConfigManager
from src.cli.common import dump_json, sha256_file, validate_input_file_exists, validate_output_parent_exists


def _get_pdf_metadata(pdf_path: str) -> Dict[str, Any]:
    import fitz  # Lazy import

    p = Path(pdf_path)
    stat = p.stat()
    # MuPDFがstdout/stderrへ警告を出すことがあるため抑制
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        with fitz.open(pdf_path) as d:
            page_count = d.page_count
    return {
        "pdf": {
            "filename": p.name,
            "path": str(p.resolve()),
            "size": stat.st_size,
            "page_count": page_count,
            "sha256": sha256_file(pdf_path),
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _structured_from_pdf(pdf_path: str) -> Dict[str, Any]:
    import fitz  # Lazy import
    pages: List[Dict[str, Any]] = []
    # MuPDFの標準出力を抑制
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                raw = page.get_text("rawdict")
                out_blocks: List[Dict[str, Any]] = []
                for block in raw.get("blocks", []) or []:
                    if "lines" not in block:
                        continue
                    lines_out: List[Dict[str, Any]] = []
                    for line in block.get("lines", []) or []:
                        spans_out: List[Dict[str, Any]] = []
                        for span in line.get("spans", []) or []:
                            spans_out.append({"text": span.get("text", ""), "bbox": span.get("bbox", None)})
                        if spans_out:
                            lines_out.append({"spans": spans_out})
                    if lines_out:
                        out_blocks.append({"lines": lines_out})
                pages.append({"page": i + 1, "blocks": out_blocks})
    return {"pages": pages}


def _blocks_plain_text(pdf_path: str) -> List[List[str]]:
    """仕様書に従い2D配列形式で返す: [["xxxx","yyyy"],["zzzz","aaa"],...]"""
    import fitz
    from src.pdf.pdf_block_mapper import PDFBlockTextMapper
    
    pages_out: List[List[str]] = []
    
    try:
        # MuPDFの標準出力を抑制
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with fitz.open(pdf_path) as doc:
                # PDFBlockTextMapperを使用してブロック単位のテキストを取得
                mapper = PDFBlockTextMapper(doc, enable_cache=True)
                
                # ページごとにブロックテキストを取得
                for page_num in range(len(doc)):
                    page_block_texts = mapper.get_page_block_texts(page_num)
                    if page_block_texts:
                        pages_out.append(page_block_texts)
    
    except Exception as e:
        print(f"ブロックテキスト抽出エラー: {e}")
        # フォールバック: 空のリストを返す
        pages_out = []
    
    return pages_out


def _read_highlight_raw(pdf_path: str, cfg: ConfigManager) -> List[Dict[str, Any]]:
    """PDFAnnotatorのそのままの出力からHighlightのみを返す（テスト期待仕様）。"""
    from src.pdf.pdf_annotator import PDFAnnotator

    annot = PDFAnnotator(cfg)
    # MuPDFの標準出力を抑制
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        anns = annot.read_pdf_annotations(pdf_path)
    return [a for a in (anns or []) if a.get("annotation_type") == "Highlight"]


def _convert_highlights_to_spec_format(highlights: List[Dict[str, Any]], structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    """ハイライトを仕様書のdetect形式に変換"""
    detect_list: List[Dict[str, Any]] = []
    for highlight in highlights:
        # ハイライトから座標情報を取得し、page_num/block_num/offsetに変換
        # 実装は座標マッピング機能完成後に詳細化
        detect_item = {
            "start": {"page_num": 0, "block_num": 0, "offset": 0},
            "end": {"page_num": 0, "block_num": 0, "offset": 0},
            "entity": highlight.get("entity", "UNKNOWN"),
            "word": highlight.get("text", ""),
            "origin": "manual"
        }
        detect_list.append(detect_item)
    return detect_list


def _read_embedded_coordinate_maps(pdf_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """PDFに埋め込まれた座標マップを読み込んで仕様書形式に変換"""
    from src.pdf.pdf_coordinate_mapper import PDFCoordinateMapper
    
    try:
        mapper = PDFCoordinateMapper()
        
        # 埋め込まれた座標マップを読み込み
        if not mapper._load_existing_coordinate_map(pdf_path):
            # 埋め込みマップが見つからない場合は空のマップを返す
            return {}, {}
        
        # PDFCoordinateMapperのデータを仕様書形式に変換
        offset2coords_map: Dict[str, Any] = {}
        coords2offset_map: Dict[str, Any] = {}
        
        # ページごとにグループ化
        page_mappings = {}
        for mapping in mapper.coordinate_mappings:
            page_num = mapping.page
            if page_num not in page_mappings:
                page_mappings[page_num] = {}
            
            block_id = mapping.block_idx
            if block_id not in page_mappings[page_num]:
                page_mappings[page_num][block_id] = []
            
            page_mappings[page_num][block_id].append(mapping)
        
        # 仕様書形式に変換
        for page_num, blocks in page_mappings.items():
            offset2coords_map[str(page_num)] = {}
            
            for block_id, mappings in blocks.items():
                block_coords = []
                
                for mapping in mappings:
                    bbox = mapping.bbox
                    block_coords.append(bbox)
                    
                    # coords2offsetMapの作成
                    coord_key = f"({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})"
                    char_offset = mapping.char_start  # 文字オフセットとして使用
                    coords2offset_map[coord_key] = f"({page_num},{block_id},{char_offset})"
                
                if block_coords:
                    offset2coords_map[str(page_num)][str(block_id)] = block_coords
        
        return offset2coords_map, coords2offset_map
        
    except Exception as e:
        print(f"埋め込み座標マップ読み込みエラー: {e}", file=sys.stderr)
        return {}, {}


def _generate_coordinate_maps(pdf_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """座標マップを生成（仕様書形式・PDFBlockTextMapper統合版）"""
    import fitz
    from src.pdf.pdf_block_mapper import PDFBlockTextMapper
    from src.pdf.pdf_coordinate_mapper import PDFCoordinateMapper
    
    # 仕様書形式: {page_num:{block_num:[[x0,y0,x1,y1],...]}}
    offset2coords_map: Dict[str, Any] = {}
    # 仕様書形式: {(x0,y0,x1,y1):(page_num,block_num,offset)}
    coords2offset_map: Dict[str, Any] = {}
    
    try:
        # まず埋め込まれた座標マップを読み込み試行
        embedded_maps = _read_embedded_coordinate_maps(pdf_path)
        if embedded_maps[0] or embedded_maps[1]:  # 埋め込みマップが見つかった場合
            print("埋め込まれた座標マップを使用します", file=sys.stderr)
            return embedded_maps
        
        # 埋め込みマップがない場合は従来の方法で生成
        print("座標マップを新規生成します", file=sys.stderr)
        
        # MuPDFの標準出力を抑制
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with fitz.open(pdf_path) as doc:
                # PDFBlockTextMapperを使用してブロック単位の座標マッピングを取得
                mapper = PDFBlockTextMapper(doc, enable_cache=True)
                
                # ページごとにブロック情報を処理
                for page_num in range(len(doc)):
                    offset2coords_map[str(page_num)] = {}
                    page_block_infos = mapper.get_page_block_summary(page_num)
                    page_block_texts = mapper.get_page_block_texts(page_num)
                    
                    for block_info in page_block_infos:
                        page_block_id = block_info["page_block_id"]
                        block_text = page_block_texts[page_block_id] if page_block_id < len(page_block_texts) else ""
                        
                        # ブロック内の各文字位置に対する座標を取得
                        block_coords = []
                        char_offset = 0
                        
                        # ブロック全体の文字範囲を処理
                        if block_text:
                            # ブロック内の各文字の座標情報を取得
                            for char_offset in range(len(block_text)):
                                char_coords = mapper.map_page_block_offset_to_coordinates(
                                    page_num, page_block_id, char_offset, char_offset + 1
                                )
                                
                                if char_coords:
                                    for coord_data in char_coords:
                                        rect = coord_data["rect"]
                                        bbox = [rect.x0, rect.y0, rect.x1, rect.y1]
                                        block_coords.append(bbox)
                                        
                                        # coords2offsetMapの作成
                                        coord_key = f"({rect.x0},{rect.y0},{rect.x1},{rect.y1})"
                                        coords2offset_map[coord_key] = f"({page_num},{page_block_id},{char_offset})"
                        
                        # ブロックに座標データがある場合のみ追加
                        if block_coords:
                            offset2coords_map[str(page_num)][str(page_block_id)] = block_coords
    
    except Exception as e:
        # エラー時は空のマップを返す
        print(f"座標マップ生成エラー: {e}")
        offset2coords_map = {}
        coords2offset_map = {}
    
    return offset2coords_map, coords2offset_map


@click.command(help="PDFを読み込み 統一スキーマのJSONをファイル出力（text.*, detect.*）")
@click.option("--pdf", type=str, required=True, help="入力PDFファイルのパス")
@click.option("--config", type=str, help="設定ファイル（readセクションのみ参照）")
@click.option("--out", type=str, required=True, help="出力先（必ず指定。標準出力は不可）")
@click.option("--pretty", is_flag=True, default=False, help="JSON整形出力")
@click.option("--with-map/--no-map", default=True, help="座標⇔文字オフセット変換マップを含める")
@click.option("--with-highlights", is_flag=True, default=False, help="既存ハイライトをdetectに含める")
def main(pdf: str, config: Optional[str], out: Optional[str], pretty: bool, with_map: bool, with_highlights: bool):
    try:
        # 入力確認
        validate_input_file_exists(pdf)
        if out:
            validate_output_parent_exists(out)

        cfg = ConfigManager()

        metadata = _get_pdf_metadata(pdf)
        
        # 仕様書に従い、まずstructured textを読み込む（structured_text読み込みは廃止予定だが座標マップ生成に必要）
        structured = _structured_from_pdf(pdf)
        
        # text は2D配列形式で出力
        text_2d = _blocks_plain_text(pdf)
        
        detect_list: List[Dict[str, Any]] = []
        if with_highlights:
            highlights = _read_highlight_raw(pdf, cfg)
            detect_list = _convert_highlights_to_spec_format(highlights, structured)
        
        # 座標マップ生成
        offset2coords_map: Dict[str, Any] = {}
        coords2offset_map: Dict[str, Any] = {}
        if with_map:
            offset2coords_map, coords2offset_map = _generate_coordinate_maps(pdf)
        
        # 仕様書の形式でJSON出力を構築
        result: Dict[str, Any] = {
            "metadata": metadata,
            "text": text_2d,
            "detect": detect_list
        }
        
        if with_map:
            result["offset2coordsMap"] = offset2coords_map
            result["coords2offsetMap"] = coords2offset_map
        
        dump_json(result, out, pretty)
    except Exception as e:
        # 例外でもファイルにJSONで返す（仕様書形式に合わせる）
        err = {"metadata": {"error": str(e)}, "text": [], "detect": []}
        # out は必須指定のため、そのまま書き出し
        dump_json(err, out, pretty)


if __name__ == "__main__":
    main()
