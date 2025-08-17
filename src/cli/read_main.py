#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

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
    """ハイライトを仕様書のdetect形式に変換（改良されたテキスト検索ベース座標マッピング付き）"""
    # 許可されたエンティティタイプ
    ALLOWED_ENTITIES = {"PERSON", "LOCATION", "DATE_TIME", "PHONE_NUMBER", "INDIVIDUAL_NUMBER", "YEAR", "PROPER_NOUN", "OTHER"}
    
    detect_list: List[Dict[str, Any]] = []
    
    # テキストブロックデータを取得
    # NOTE: 期待する形式は 2次元配列（page_num -> [block_text, ...]）。
    # これまで structured_from_pdf の戻りは {"pages": ...} で、"text" を持たず常に [[ ]] になっていたため
    # 検索が行われず page_num/block_num/offset が 0 のままになる不具合があった。
    # 呼び出し側から {"text": text_2d} を渡す前提に変更し、未提供時は空配列にする。
    text_blocks = structured.get("text") or []
    
    # 既に使用された位置を追跡（重複回避のため）
    used_positions = set()
    
    for highlight in highlights:
        # Creator情報の確認
        creator = highlight.get("creator", "")
        origin = "auto" if creator == "origin" else "manual"
        
        # コンテンツからdetect_wordとentity_typeを抽出
        detect_word = ""
        entity_type = ""
        
        # 新しい埋め込み形式をパース
        if "detect_word" in highlight and "entity_type" in highlight:
            detect_word = highlight["detect_word"]
            entity_type = highlight["entity_type"]
        else:
            # 従来の形式から取得
            entity_type = highlight.get("title", "UNKNOWN")
            detect_word = highlight.get("content", "")
        
        # エンティティタイプの検証
        if entity_type not in ALLOWED_ENTITIES:
            continue  # 許可されていないエンティティは読み取らない
        
        if not detect_word:
            continue  # テキストが空の場合は読み取らない
            
        # テキスト検索ベースで位置を特定
        start_pos = {"page_num": 0, "block_num": 0, "offset": 0}
        end_pos = {"page_num": 0, "block_num": 0, "offset": 0}
        
        # 全てのテキストブロックから detect_word の全ての出現位置を検索
        found = False
        candidates = []
        
        for page_num, page_blocks in enumerate(text_blocks):
            for block_num, block_text in enumerate(page_blocks):
                # 指定した単語の全ての出現位置を検索
                start_index = 0
                while True:
                    offset = block_text.find(detect_word, start_index)
                    if offset == -1:
                        break
                    
                    position_key = (page_num, block_num, offset)
                    if position_key not in used_positions:
                        candidates.append({
                            'page_num': page_num,
                            'block_num': block_num, 
                            'offset': offset,
                            'end_offset': offset + len(detect_word) - 1
                        })
                    
                    start_index = offset + 1
        
        # 最適な候補を選択（最初の未使用位置）
        if candidates:
            best_candidate = candidates[0]
            start_pos = {
                "page_num": best_candidate['page_num'], 
                "block_num": best_candidate['block_num'], 
                "offset": best_candidate['offset']
            }
            end_pos = {
                "page_num": best_candidate['page_num'], 
                "block_num": best_candidate['block_num'], 
                "offset": best_candidate['end_offset']
            }
            
            # この位置を使用済みとしてマーク
            position_key = (best_candidate['page_num'], best_candidate['block_num'], best_candidate['offset'])
            used_positions.add(position_key)
            found = True
        
        # マッチが見つかった場合のみ追加（デフォルト0のまま出力しない）
        if found:
            detect_item = {
                "start": start_pos,
                "end": end_pos,
                "entity": entity_type,
                "word": detect_word,
                "origin": origin
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
        
        # 進捗ログ（概要）
        total_pages = len(page_mappings)
        total_blocks = sum(len(b) for b in page_mappings.values())
        logging.debug(
            "埋め込み座標マップを読み取り: ページ=%d, ブロック=%d",
            total_pages,
            total_blocks,
        )

        return offset2coords_map, coords2offset_map
        
    except Exception as e:
        print(f"埋め込み座標マップ読み込みエラー: {e}", file=sys.stderr)
        return {}, {}


def _generate_coordinate_maps(pdf_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """座標マップを新規生成する（常に生成。埋め込みは参照しない）"""
    import fitz
    from src.pdf.pdf_block_mapper import PDFBlockTextMapper
    from src.pdf.pdf_coordinate_mapper import PDFCoordinateMapper
    
    # 仕様書形式: {page_num:{block_num:[[x0,y0,x1,y1],...]}}
    offset2coords_map: Dict[str, Any] = {}
    # 仕様書形式: {(x0,y0,x1,y1):(page_num,block_num,offset)}
    coords2offset_map: Dict[str, Any] = {}
    
    try:
        # MuPDFの標準出力を抑制
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with fitz.open(pdf_path) as doc:
                # PDFBlockTextMapperを使用してブロック単位の座標マッピングを取得
                mapper = PDFBlockTextMapper(doc, enable_cache=True)

                total_pages = len(doc)
                logging.debug("座標マップ生成開始: 総ページ数=%d", total_pages)
                # ページごとの処理進捗を表示（stderr）。TTYでない場合も安全に動作。
                label = "座標マップ生成中: ページ処理"
                iterable = range(total_pages)
                with click.progressbar(iterable, label=label, file=sys.stderr, length=total_pages) as bar:
                    for page_num in bar:
                        blocks_processed = 0
                        coords_emitted = 0
                        offset2coords_map[str(page_num)] = {}
                        page_block_texts = mapper.get_page_block_texts(page_num)
                        page_mapping = mapper.page_block_offset_mapping.get(page_num, {})
                        for page_block_id, offset_map in page_mapping.items():
                            block_text = page_block_texts[page_block_id] if page_block_id < len(page_block_texts) else ""
                            if not block_text:
                                continue
                            blocks_processed += 1
                            block_coords: List[List[float]] = []
                            for char_offset in range(len(block_text)):
                                idx = offset_map.get(char_offset)
                                if idx is None:
                                    continue
                                char_pos = mapper.char_positions[idx]
                                if not char_pos.bbox:
                                    continue
                                x0, y0, x1, y1 = char_pos.bbox
                                bbox = [x0, y0, x1, y1]
                                block_coords.append(bbox)
                                coord_key = f"({x0},{y0},{x1},{y1})"
                                coords2offset_map[coord_key] = f"({page_num},{page_block_id},{char_offset})"
                                coords_emitted += 1
                            if block_coords:
                                offset2coords_map[str(page_num)][str(page_block_id)] = block_coords
                        logging.debug(
                            "ページ処理完了: %d/%d, ブロック=%d, 生成座標=%d",
                            page_num + 1,
                            total_pages,
                            blocks_processed,
                            coords_emitted,
                        )
    
    except Exception as e:
        # エラー時は空のマップを返す
        print(f"座標マップ生成エラー: {e}")
        offset2coords_map = {}
        coords2offset_map = {}
    
    return offset2coords_map, coords2offset_map


@click.command(help="PDFを読み込み 統一スキーマのJSONをファイル出力（text.*, detect.*）")
@click.option("--pdf", type=str, required=True, help="入力PDFファイルのパス")
@click.option("--out", type=str, required=True, help="出力先（必ず指定。標準出力は不可）")
@click.option("--pretty", is_flag=True, default=False, help="JSON整形出力")
@click.option(
    "--with-map/--no-map",
    default=True,
    help="座標マップを出力へ含めるか（Trueなら埋め込みを優先し、無ければ生成）",
)
@click.option("--with-highlights/--no-highlights", default=True, help="既存ハイライトをdetectに含める（デフォルトON）")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="WARNING",
    show_default=True,
    help="ログレベル（進捗はDEBUGで表示）",
)
def main(pdf: str, out: Optional[str], pretty: bool, with_map: bool, with_highlights: bool, log_level: str = "WARNING"):
    try:
        # ログ設定（stderrへ出力）
        logging.basicConfig(
            level=getattr(logging, str(log_level).upper(), logging.WARNING),
            format="%(asctime)s %(levelname)s [read]: %(message)s",
        )
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
            # ハイライト位置推定は 2Dテキスト配列を用いて行う
            detect_list = _convert_highlights_to_spec_format(highlights, {"text": text_2d})
        
        # 座標マップ: --with-map のときのみ出力へ含める
        offset2coords_map: Dict[str, Any] = {}
        coords2offset_map: Dict[str, Any] = {}
        if with_map:
            embedded_maps: Tuple[Dict[str, Any], Dict[str, Any]] = _read_embedded_coordinate_maps(pdf)
            if embedded_maps[0] or embedded_maps[1]:
                print("埋め込まれた座標マップを使用します", file=sys.stderr)
                logging.debug("埋め込みマップ利用を選択")
                offset2coords_map, coords2offset_map = embedded_maps
            else:
                print("座標マップを新規生成します", file=sys.stderr)
                logging.debug("座標マップの新規生成を開始")
                offset2coords_map, coords2offset_map = _generate_coordinate_maps(pdf)
        
        # 仕様書の形式でJSON出力を構築
        result: Dict[str, Any] = {
            "metadata": metadata,
            "text": text_2d,
            "detect": detect_list
        }
        
        # --with-map の場合のみマップを含める（空でなければ）
        if with_map and offset2coords_map:
            result["offset2coordsMap"] = offset2coords_map
        if with_map and coords2offset_map:
            result["coords2offsetMap"] = coords2offset_map
        
        dump_json(result, out, pretty)
    except Exception as e:
        # 例外でもファイルにJSONで返す（仕様書形式に合わせる）
        err = {"metadata": {"error": str(e)}, "text": [], "detect": []}
        # out は必須指定のため、そのまま書き出し
        dump_json(err, out, pretty)


if __name__ == "__main__":
    main()
