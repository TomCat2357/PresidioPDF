"""
PresidioPDF PyQt - Pipeline Service

Phase 2: 既存CLIロジックの再利用
- read/detect処理を呼び出し可能な形で提供
- UIから独立した処理ロジック

Phase 5: エラーハンドリング強化
- 入力検証の追加
- より具体的なエラーメッセージ
- ロギングの追加
"""

import json
import sys
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ロガーの設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 既存CLIモジュールのインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.cli.read_main import (
    _get_pdf_metadata,
    _structured_from_pdf,
    _blocks_plain_text,
    _generate_coordinate_maps,
)
from src.core.config_manager import ConfigManager


class PipelineService:
    """PresidioPDFの処理パイプラインを提供するサービスクラス

    既存のCLIロジックを再利用し、GUI向けに整形された結果を返す。
    """

    @staticmethod
    def run_read(pdf_path: Path, include_coordinate_map: bool = True) -> Dict[str, Any]:
        """PDF読込処理（read）

        Args:
            pdf_path: 処理対象のPDFファイルパス
            include_coordinate_map: 座標マップを含めるか

        Returns:
            read結果のJSON（dict）

        Raises:
            FileNotFoundError: PDFファイルが見つからない場合
            ValueError: 無効なPDFファイルの場合
            Exception: その他のPDF読込エラー
        """
        logger.info(f"run_read開始: {pdf_path}")

        # 入力検証
        if not isinstance(pdf_path, Path):
            logger.error(f"無効なパス型: {type(pdf_path)}")
            raise TypeError(f"pdf_pathはPathオブジェクトである必要があります: {type(pdf_path)}")

        if not pdf_path.exists():
            logger.error(f"ファイルが見つかりません: {pdf_path}")
            raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")

        if not pdf_path.is_file():
            logger.error(f"ディレクトリが指定されています: {pdf_path}")
            raise ValueError(f"PDFファイルではありません: {pdf_path}")

        if pdf_path.suffix.lower() != '.pdf':
            logger.warning(f"PDF以外のファイル拡張子: {pdf_path.suffix}")

        pdf_str = str(pdf_path.resolve())

        # メタデータ取得
        metadata = _get_pdf_metadata(pdf_str)

        # 構造化データ取得（将来の参照用、現在は使用しない）
        # structured = _structured_from_pdf(pdf_str)

        # プレーンテキスト取得（2D配列）
        text_2d = _blocks_plain_text(pdf_str)

        # 座標マップの生成（オプション）
        offset2coords_map = {}
        coords2offset_map = {}
        if include_coordinate_map:
            try:
                offset2coords_map, coords2offset_map = _generate_coordinate_maps(pdf_str)
                logger.debug("座標マップの生成完了")
            except Exception as e:
                logger.warning(f"座標マップの生成に失敗: {e}")
                # 座標マップなしで継続

        # 結果の組み立て（CLI互換形式）
        result = {
            "metadata": metadata,
            "text": text_2d,
            "detect": [],  # read時点ではdetect結果は空
        }

        # 座標マップを追加
        if offset2coords_map:
            result["offset2coordsMap"] = offset2coords_map
        if coords2offset_map:
            result["coords2offsetMap"] = coords2offset_map

        page_count = metadata.get("pdf", {}).get("page_count", len(text_2d))
        logger.info(f"run_read完了: {page_count} ページ")
        return result

    @staticmethod
    def run_detect(
        read_result: Dict[str, Any],
        entities: Optional[List[str]] = None,
        model_names: Optional[Tuple[str, ...]] = None,
        use_predetect: bool = True,
        add_patterns: Optional[List[Tuple[str, str]]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """PII検出処理（detect）

        Args:
            read_result: run_readの結果
            entities: 検出対象のエンティティリスト（省略時は設定ファイルから）
            model_names: 使用するモデル名のタプル（省略時は設定ファイルから）
            use_predetect: 事前検出を使用するか
            add_patterns: 追加パターン [(entity_type, regex), ...]
            exclude_patterns: 除外パターン [regex, ...]

        Returns:
            detect結果のJSON（dict）

        Raises:
            ValueError: read_resultが不正な場合
            FileNotFoundError: PDFファイルが見つからない場合
            Exception: 検出処理に失敗した場合
        """
        logger.info("run_detect開始")

        import re
        import json
        from datetime import datetime
        from src.analysis.analyzer import Analyzer
        import fitz
        from src.pdf.pdf_locator import PDFTextLocator
        from src.cli.detect_main import _convert_offsets_to_position, ALLOWED_ENTITIES
        from src.cli.common import sha256_bytes

        # 入力検証
        if not isinstance(read_result, dict):
            logger.error(f"read_resultが辞書型ではありません: {type(read_result)}")
            raise TypeError("read_resultは辞書型である必要があります")

        # 設定マネージャの初期化
        cfg = ConfigManager()

        # エンティティの決定
        if entities is None:
            entities = cfg.get_enabled_entities()

        # モデルの決定
        if model_names is None:
            model_names = cfg.get_models()

        # read_resultからテキストとメタデータを取得
        metadata = read_result.get("metadata", {}) or {}
        pdf_path = (metadata.get("pdf", {}) or {}).get("path")

        if not pdf_path:
            logger.error("PDFパスがread_resultに含まれていません")
            raise ValueError("metadata.pdf.path にPDFの絶対パスが必要です")

        if not Path(pdf_path).exists():
            logger.error(f"PDFファイルが見つかりません: {pdf_path}")
            raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")

        text_2d = read_result.get("text", [])

        # 2D配列をフラット化してプレーンテキストを生成
        plain_text = None
        if isinstance(text_2d, list) and text_2d:
            try:
                full_plain_text_parts = []
                for page_blocks in text_2d:
                    if isinstance(page_blocks, list):
                        for block in page_blocks:
                            full_plain_text_parts.append(str(block))
                plain_text = "".join(full_plain_text_parts)
            except Exception:
                plain_text = None

        # Analyzerでモデル検出
        analyzer = Analyzer(cfg)
        detections_plain = []

        with fitz.open(pdf_path) as doc:
            locator = PDFTextLocator(doc)
            target_text = plain_text if isinstance(plain_text, str) else locator.full_text_no_newlines

            # モデル検出
            model_results = analyzer.analyze_text(target_text, entities)

            for r in model_results:
                ent = r.get("entity_type") or r.get("entity")
                s = int(r["start"])
                e = int(r["end"])
                txt = target_text[s:e]

                # 位置情報を変換
                start_pos, end_pos = _convert_offsets_to_position(s, e, text_2d)
                entry_plain = {
                    "start": start_pos,
                    "end": end_pos,
                    "entity": ent,
                    "word": txt,
                    "origin": "auto"
                }
                detections_plain.append(entry_plain)

            # 追加パターンの検出
            if add_patterns:
                for ent_name, rx_str in add_patterns:
                    try:
                        rx = re.compile(rx_str)
                        for m in rx.finditer(target_text):
                            s, e = m.start(), m.end()
                            txt = target_text[s:e]
                            start_pos, end_pos = _convert_offsets_to_position(s, e, text_2d)
                            detections_plain.append({
                                "start": start_pos,
                                "end": end_pos,
                                "entity": ent_name,
                                "word": txt,
                                "origin": "custom"
                            })
                    except re.error:
                        # 無効な正規表現はスキップ
                        pass

            # 除外パターンの適用
            if exclude_patterns:
                exclude_spans = []
                for rx_str in exclude_patterns:
                    try:
                        rx = re.compile(rx_str)
                        for m in rx.finditer(target_text):
                            exclude_spans.append((m.start(), m.end()))
                    except re.error:
                        pass

                if exclude_spans:
                    def is_auto(entry: Dict[str, Any]) -> bool:
                        return entry.get("origin") == "auto"

                    # 除外は自動検出のみに適用（簡略化）
                    detections_plain = [
                        d for d in detections_plain
                        if not is_auto(d)
                    ]

        # 既存検出情報の統合
        existing_detect = read_result.get("detect", [])
        if use_predetect and isinstance(existing_detect, list):
            merged_detect = list(existing_detect) + detections_plain
        else:
            merged_detect = detections_plain

        # 座標マップの継承
        offset2coords_map = read_result.get("offset2coordsMap", {})
        coords2offset_map = read_result.get("coords2offsetMap", {})

        # metadataの更新
        out_metadata = dict(metadata)
        out_metadata["generated_at"] = datetime.utcnow().isoformat() + "Z"

        # 結果の構築
        result = {
            "metadata": out_metadata,
            "detect": merged_detect,
            "text": text_2d,
        }

        if offset2coords_map:
            result["offset2coordsMap"] = offset2coords_map
        if coords2offset_map:
            result["coords2offsetMap"] = coords2offset_map

        logger.info(f"run_detect完了: {len(merged_detect)} 件の検出")
        return result

    @staticmethod
    def run_duplicate(
        detect_result: Dict[str, Any],
        overlap: str = "overlap",
        entity_overlap_mode: str = "same",
        entity_priority: Optional[List[str]] = None,
        tie_break: Optional[List[str]] = None,
        origin_priority: Optional[List[str]] = None,
        length_pref: str = "long",
        position_pref: str = "first",
    ) -> Dict[str, Any]:
        """重複処理（duplicate）

        Args:
            detect_result: run_detectの結果
            overlap: 重複の定義 ("exact", "contain", "overlap")
            entity_overlap_mode: エンティティ種類を考慮 ("same", "any")
            entity_priority: エンティティ優先順
            tie_break: タイブレーク順
            origin_priority: 検出由来の優先順
            length_pref: 長短の優先 ("long", "short")
            position_pref: 位置の優先 ("first", "last")

        Returns:
            重複処理後の結果
        """
        logger.info("run_duplicate開始")

        from src.cli.duplicate_main import _dedupe_detections_spec_format

        # 入力検証
        if not isinstance(detect_result, dict):
            logger.error(f"detect_resultが辞書型ではありません: {type(detect_result)}")
            raise TypeError("detect_resultは辞書型である必要があります")

        # デフォルト値の設定
        if entity_priority is None:
            entity_priority = ["PERSON", "LOCATION", "DATE_TIME", "PHONE_NUMBER",
                             "INDIVIDUAL_NUMBER", "YEAR", "PROPER_NOUN", "OTHER"]
        if tie_break is None:
            tie_break = ["origin", "length", "position", "entity"]
        if origin_priority is None:
            origin_priority = ["manual", "custom", "auto"]

        # detect配列を取得
        detect_list = detect_result.get("detect", [])
        if not isinstance(detect_list, list):
            detect_list = []

        # 重複処理の実行
        result_detect = _dedupe_detections_spec_format(
            detect_list,
            overlap=overlap,
            entity_overlap_mode=entity_overlap_mode,
            entity_priority=entity_priority,
            tie_break=tie_break,
            origin_priority=origin_priority,
            length_pref=length_pref,
            position_pref=position_pref,
        )

        # 結果の構築
        result = {
            "metadata": detect_result.get("metadata", {}),
            "detect": result_detect,
        }

        # 座標マップとテキストの継承
        if "offset2coordsMap" in detect_result:
            result["offset2coordsMap"] = detect_result["offset2coordsMap"]
        if "coords2offsetMap" in detect_result:
            result["coords2offsetMap"] = detect_result["coords2offsetMap"]
        if "text" in detect_result:
            result["text"] = detect_result["text"]

        logger.info(f"run_duplicate完了: {len(detect_list)} → {len(result_detect)} 件")
        return result

    @staticmethod
    def run_mask(
        detect_result: Dict[str, Any],
        pdf_path: Path,
        output_path: Path,
        mask_styles: Optional[Dict[str, Dict[str, float]]] = None,
        embed_coordinates: bool = False,
    ) -> Dict[str, Any]:
        """マスキング処理（mask）

        Args:
            detect_result: run_detectまたはrun_duplicateの結果
            pdf_path: 元のPDFファイルパス
            output_path: 出力先PDFファイルパス
            mask_styles: エンティティ別のマスクスタイル {entity_type: {r, g, b, a}}
            embed_coordinates: 座標マップを埋め込むか

        Returns:
            マスキング処理の結果
        """
        logger.info(f"run_mask開始: {pdf_path} → {output_path}")

        import fitz
        from src.pdf.pdf_locator import PDFTextLocator

        # 入力検証
        if not isinstance(detect_result, dict):
            logger.error(f"detect_resultが辞書型ではありません: {type(detect_result)}")
            raise TypeError("detect_resultは辞書型である必要があります")

        if not Path(pdf_path).exists():
            logger.error(f"入力PDFファイルが見つかりません: {pdf_path}")
            raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")

        # detect配列を取得
        detect_list = detect_result.get("detect", [])
        if not isinstance(detect_list, list):
            detect_list = []

        # 座標・テキスト情報の取得
        offset2coords_map = detect_result.get("offset2coordsMap", {})
        text_2d = detect_result.get("text", [])

        # グローバルオフセットマップの準備
        block_start_global = {}
        global_cursor = 0
        if isinstance(text_2d, list):
            for p, page_blocks in enumerate(text_2d):
                if not isinstance(page_blocks, list):
                    continue
                for b, block_text in enumerate(page_blocks):
                    s = str(block_text or "")
                    block_start_global[(p, b)] = global_cursor
                    global_cursor += len(s)

        # マスク対象（ページ・矩形・置換文字列）の構築
        redactions: List[Dict[str, Any]] = []

        def _normalize_entity_key(name: str) -> str:
            n = str(name or "").strip()
            if not n:
                return ""
            low = n.lower()
            if low == "address":
                return "LOCATION"
            return n.upper()

        def _group_rects_by_line(rects: List[List[float]], y_threshold: float = 2.0) -> List[List[float]]:
            """同一行の矩形をy座標でグルーピングして各行の外接矩形を返す"""
            if not rects:
                return []
            items = []
            for r in rects:
                try:
                    x0, y0, x1, y1 = map(float, r)
                    cy = (y0 + y1) / 2.0
                    items.append((cy, [x0, y0, x1, y1]))
                except Exception:
                    continue
            items.sort(key=lambda t: t[0])
            groups = []
            for cy, rect in items:
                if not groups:
                    groups.append([rect])
                    continue
                last_group = groups[-1]
                gcy = sum(((rr[1] + rr[3]) / 2.0) for rr in last_group) / len(last_group)
                if abs(cy - gcy) <= y_threshold:
                    last_group.append(rect)
                else:
                    groups.append([rect])
            out = []
            for grp in groups:
                xs0 = [rr[0] for rr in grp]
                ys0 = [rr[1] for rr in grp]
                xs1 = [rr[2] for rr in grp]
                ys1 = [rr[3] for rr in grp]
                out.append([min(xs0), min(ys0), max(xs1), max(ys1)])
            return out

        def _mask_text_with_question(text: str) -> str:
            """テキストを?置換する（空白は維持）"""
            s = str(text or "")
            masked = "".join("?" if not ch.isspace() else ch for ch in s).strip()
            return masked if masked else "?"

        with fitz.open(str(pdf_path)) as doc:
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

                # グローバルオフセットに変換してline_rectsを取得
                line_rects_items = []
                try:
                    key_s = (page_num, block_num)
                    key_e = (end_pos.get("page_num", page_num), end_pos.get("block_num", block_num))
                    if key_s in block_start_global and key_e in block_start_global:
                        start_global = block_start_global[key_s] + int(start_offset)
                        end_global_excl = block_start_global[key_e] + int(end_offset) + 1
                        line_rects_items = locator.get_pii_line_rects(start_global, end_global_excl)
                except Exception:
                    line_rects_items = []

                # フォールバック: offset2coordsMap
                if not line_rects_items and offset2coords_map:
                    try:
                        ps = int(start_pos.get("page_num", 0))
                        pe = int(end_pos.get("page_num", ps))
                        bs = int(start_pos.get("block_num", 0))
                        be = int(end_pos.get("block_num", bs))
                        os = int(start_offset)
                        oe = int(end_offset)

                        page_rects = {}
                        for p in range(ps, pe + 1):
                            page_dict = offset2coords_map.get(str(p), {})
                            if not isinstance(page_dict, dict) or not page_dict:
                                continue
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
                    replacement_text = _mask_text_with_question(text)
                    for idx, item in enumerate(line_rects_items):
                        rect_info = item.get("rect", {})
                        try:
                            x0 = float(rect_info["x0"])
                            y0 = float(rect_info["y0"])
                            x1 = float(rect_info["x1"])
                            y1 = float(rect_info["y1"])
                        except Exception:
                            continue
                        if x1 <= x0 or y1 <= y0:
                            continue
                        redactions.append(
                            {
                                "page_num": int(item.get("page_num", page_num)),
                                "rect": [x0, y0, x1, y1],
                                "replace_text": replacement_text if idx == 0 else "?",
                                "entity_type": _normalize_entity_key(entity_type),
                            }
                        )

        # PDFに黒塗り + ?置換を適用
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with fitz.open(str(pdf_path)) as out_doc:
            redaction_count = 0

            # ページ単位でredactionを追加・適用
            redactions_by_page: Dict[int, List[Dict[str, Any]]] = {}
            for item in redactions:
                redactions_by_page.setdefault(int(item["page_num"]), []).append(item)

            for page_num, page_redactions in redactions_by_page.items():
                if page_num < 0 or page_num >= len(out_doc):
                    continue
                page = out_doc[page_num]

                for item in page_redactions:
                    rect = fitz.Rect(item["rect"]) & page.rect
                    if (not rect) or rect.width <= 0 or rect.height <= 0:
                        continue

                    replace_text = item.get("replace_text") or "?"
                    try:
                        page.add_redact_annot(
                            rect,
                            text=replace_text,
                            fill=(0, 0, 0),        # 黒塗り
                            text_color=(1, 1, 1),  # 置換文字は白
                            fontsize=8,
                            align=0,
                        )
                    except TypeError:
                        # 互換: 古いPyMuPDFでは一部引数が使えない
                        page.add_redact_annot(rect, text=replace_text, fill=(0, 0, 0))
                    redaction_count += 1

                # 追加したredactionをこのページへ反映
                page.apply_redactions()

            out_doc.save(str(output_path), garbage=4, deflate=True, clean=True)

        # 座標マップの埋め込み
        if embed_coordinates:
            try:
                from src.pdf.pdf_coordinate_mapper import PDFCoordinateMapper
                mapper = PDFCoordinateMapper()
                if mapper.load_or_create_coordinate_map(str(pdf_path)):
                    temp_path = str(output_path) + ".temp"
                    if mapper.save_pdf_with_coordinate_map(str(output_path), temp_path):
                        Path(temp_path).replace(output_path)
            except Exception:
                # 埋め込み失敗は無視
                logger.warning(f"座標マップの埋め込みに失敗")
                pass

        logger.info(f"run_mask完了: {redaction_count} 件のマスキング")
        return {
            "output_path": str(output_path),
            "entity_count": redaction_count,
            "success": True,
        }
