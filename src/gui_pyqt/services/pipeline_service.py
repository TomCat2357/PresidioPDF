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
        page_filter: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """PII検出処理（detect）

        Args:
            read_result: run_readの結果
            entities: 検出対象のエンティティリスト（省略時は設定ファイルから）
            model_names: 使用するモデル名のタプル（省略時は設定ファイルから）
            use_predetect: 事前検出を使用するか
            add_patterns: 追加パターン [(entity_type, regex), ...]
            exclude_patterns: 除外パターン [regex, ...]
            page_filter: 検出対象ページ番号（0始まり、Noneで全ページ）

        Returns:
            detect結果のJSON（dict）

        Raises:
            ValueError: read_resultが不正な場合
            FileNotFoundError: PDFファイルが見つからない場合
            Exception: 検出処理に失敗した場合
        """
        logger.info("run_detect開始")

        import re
        from datetime import datetime
        from src.analysis.analyzer import Analyzer
        import fitz
        from src.pdf.pdf_locator import PDFTextLocator
        from src.cli.detect_main import _convert_offsets_to_position

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
        if model_names is not None and model_names:
            cfg.set_spacy_model(model_names[0])
            model_names = cfg.get_models()
        else:
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
        target_pages: Optional[set] = None
        if page_filter is not None:
            target_pages = {
                int(page_num)
                for page_num in page_filter
                if isinstance(page_num, int) or str(page_num).lstrip("-").isdigit()
            }
            target_pages = {page_num for page_num in target_pages if page_num >= 0}

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
        compiled_excludes = []
        exclude_spans: List[Tuple[int, int]] = []

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
                if (
                    target_pages is not None
                    and int(start_pos.get("page_num", -1)) not in target_pages
                ):
                    continue
                entry_plain = {
                    "start": start_pos,
                    "end": end_pos,
                    "entity": ent,
                    "word": txt,
                    "origin": "auto",
                    "_span": (s, e),
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
                            if (
                                target_pages is not None
                                and int(start_pos.get("page_num", -1)) not in target_pages
                            ):
                                continue
                            detections_plain.append({
                                "start": start_pos,
                                "end": end_pos,
                                "entity": ent_name,
                                "word": txt,
                                "origin": "custom",
                                "_span": (s, e),
                            })
                    except re.error as exc:
                        # 無効な正規表現はスキップ
                        logger.warning(f"無効な追加正規表現をスキップ: {rx_str} ({exc})")

            # 除外パターンのマッチ範囲を収集
            if exclude_patterns:
                for rx_str in exclude_patterns:
                    try:
                        rx = re.compile(rx_str)
                        compiled_excludes.append(rx)
                        for m in rx.finditer(target_text):
                            exclude_spans.append((m.start(), m.end()))
                    except re.error as exc:
                        logger.warning(f"無効な除外正規表現をスキップ: {rx_str} ({exc})")

        # 既存検出情報の統合
        existing_detect = read_result.get("detect", [])
        if use_predetect and isinstance(existing_detect, list):
            merged_detect = list(existing_detect) + detections_plain
        else:
            merged_detect = detections_plain

        # ommitはaddより優先: 最終検出結果に対して除外を適用
        if compiled_excludes:
            def overlaps(span_a: Tuple[int, int], span_b: Tuple[int, int]) -> bool:
                return max(span_a[0], span_b[0]) < min(span_a[1], span_b[1])

            def should_omit(entry: Dict[str, Any]) -> bool:
                # 手動マークはユーザー編集を優先して除外しない
                if str(entry.get("origin", "")).lower() == "manual":
                    return False

                word = str(entry.get("word", ""))
                for rx in compiled_excludes:
                    if rx.search(word):
                        return True

                span = entry.get("_span")
                if isinstance(span, tuple) and len(span) == 2:
                    try:
                        current_span = (int(span[0]), int(span[1]))
                    except (TypeError, ValueError):
                        return False
                    if any(overlaps(current_span, ex_span) for ex_span in exclude_spans):
                        return True

                return False

            filtered_detect: List[Any] = []
            for detection in merged_detect:
                if not isinstance(detection, dict):
                    filtered_detect.append(detection)
                    continue
                if should_omit(detection):
                    continue
                filtered_detect.append(detection)
            merged_detect = filtered_detect

        for detection in merged_detect:
            if isinstance(detection, dict):
                detection.pop("_span", None)

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
        entity_overlap_mode: str = "any",
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
            tie_break = ["origin", "contain", "length", "position", "entity"]
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
            text_2d=detect_result.get("text", []),
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

        # マスク対象（ページ・矩形）の構築
        redactions: List[Dict[str, Any]] = []
        circle_masks: List[Dict[str, Any]] = []
        # 画像マスク（mask_rects_pdf）で指定された領域。重複テキストマスクの排除に使う。
        mask_redactions_by_page: Dict[int, List[List[float]]] = {}

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

        def _normalize_rect(rect: Any) -> Optional[List[float]]:
            """矩形入力を [x0, y0, x1, y1] へ正規化"""
            if not isinstance(rect, (list, tuple)) or len(rect) < 4:
                return None
            try:
                x0, y0, x1, y1 = map(float, rect[:4])
            except Exception:
                return None
            if x1 <= x0 or y1 <= y0:
                return None
            return [x0, y0, x1, y1]

        def _normalize_circle(circle: Any, default_page_num: int) -> Optional[Dict[str, Any]]:
            """円入力を {page_num, center_x, center_y, radius, rect} へ正規化"""
            page_num = int(default_page_num)
            center_x = None
            center_y = None
            radius = None

            if isinstance(circle, dict):
                try:
                    page_num = int(circle.get("page_num", page_num) or page_num)
                except Exception:
                    page_num = int(default_page_num)
                center = circle.get("center")
                if isinstance(center, (list, tuple)) and len(center) >= 2:
                    try:
                        center_x = float(center[0])
                        center_y = float(center[1])
                    except Exception:
                        center_x = None
                        center_y = None
                if center_x is None or center_y is None:
                    try:
                        center_x = float(circle.get("center_x"))
                        center_y = float(circle.get("center_y"))
                    except Exception:
                        center_x = None
                        center_y = None
                try:
                    radius = float(circle.get("radius"))
                except Exception:
                    radius = None
            elif isinstance(circle, (list, tuple)) and len(circle) >= 3:
                try:
                    center_x = float(circle[0])
                    center_y = float(circle[1])
                    radius = float(circle[2])
                except Exception:
                    center_x = None
                    center_y = None
                    radius = None

            if center_x is None or center_y is None or radius is None or radius <= 0.0:
                return None

            return {
                "page_num": page_num,
                "center_x": center_x,
                "center_y": center_y,
                "radius": radius,
                "rect": [
                    center_x - radius,
                    center_y - radius,
                    center_x + radius,
                    center_y + radius,
                ],
            }

        def _rects_intersect(a: List[float], b: List[float]) -> bool:
            """2矩形の交差判定"""
            ax0, ay0, ax1, ay1 = a
            bx0, by0, bx1, by1 = b
            ix0, iy0 = max(ax0, bx0), max(ay0, by0)
            ix1, iy1 = min(ax1, bx1), min(ay1, by1)
            return (ix1 - ix0) > 0 and (iy1 - iy0) > 0

        def _is_mask_covered(page_num: int, rect: List[float]) -> bool:
            """画像マスク領域と重なるテキストマスクは除外"""
            for mask_rect in mask_redactions_by_page.get(int(page_num), []):
                if _rects_intersect(mask_rect, rect):
                    return True
            return False

        with fitz.open(str(pdf_path)) as doc:
            locator = PDFTextLocator(doc)

            # 1st pass: 画像マスク指定（mask_rects_pdf）を先に収集
            for detect_item in detect_list:
                if not isinstance(detect_item, dict):
                    continue

                start_pos = detect_item.get("start", {})
                entity_type = detect_item.get("entity", "PII")
                normalized_entity_type = _normalize_entity_key(entity_type) or "PII"

                default_page_num = int(detect_item.get("page_num", 0) or 0)
                if isinstance(start_pos, dict):
                    try:
                        default_page_num = int(
                            start_pos.get("page_num", default_page_num) or default_page_num
                        )
                    except Exception:
                        pass

                has_circle_masks = False
                mask_circles_pdf = detect_item.get("mask_circles_pdf")
                if isinstance(mask_circles_pdf, list) and mask_circles_pdf:
                    for raw_circle in mask_circles_pdf:
                        normalized_circle = _normalize_circle(raw_circle, default_page_num)
                        if not normalized_circle:
                            continue
                        has_circle_masks = True
                        circle_masks.append(
                            {
                                "page_num": normalized_circle["page_num"],
                                "center_x": normalized_circle["center_x"],
                                "center_y": normalized_circle["center_y"],
                                "radius": normalized_circle["radius"],
                                "entity_type": normalized_entity_type,
                            }
                        )
                        mask_redactions_by_page.setdefault(
                            normalized_circle["page_num"], []
                        ).append(normalized_circle["rect"])

                selection_mode = str(detect_item.get("selection_mode", "") or "").lower()
                mask_rects_pdf = detect_item.get("mask_rects_pdf")
                if not isinstance(mask_rects_pdf, list) or not mask_rects_pdf:
                    continue
                if selection_mode == "circle_drag" and has_circle_masks:
                    # 円選択で保存された矩形外接は重複追加しない
                    continue

                for raw_rect in mask_rects_pdf:
                    rect_page_num = default_page_num
                    rect_source = raw_rect
                    if isinstance(raw_rect, dict):
                        try:
                            rect_page_num = int(raw_rect.get("page_num", rect_page_num) or rect_page_num)
                        except Exception:
                            rect_page_num = default_page_num
                        if "rect" in raw_rect:
                            rect_source = raw_rect.get("rect")
                        else:
                            rect_source = [
                                raw_rect.get("x0"),
                                raw_rect.get("y0"),
                                raw_rect.get("x1"),
                                raw_rect.get("y1"),
                            ]

                    normalized_rect = _normalize_rect(rect_source)
                    if not normalized_rect:
                        continue

                    redactions.append(
                        {
                            "page_num": rect_page_num,
                            "rect": normalized_rect,
                            "entity_type": normalized_entity_type,
                        }
                    )
                    mask_redactions_by_page.setdefault(rect_page_num, []).append(normalized_rect)

            # 2nd pass: 通常テキストマスク（画像マスク領域と重なるものは除外）
            for detect_item in detect_list:
                if not isinstance(detect_item, dict):
                    continue

                has_mask_rects = isinstance(detect_item.get("mask_rects_pdf"), list) and detect_item.get("mask_rects_pdf")
                has_mask_circles = isinstance(detect_item.get("mask_circles_pdf"), list) and detect_item.get("mask_circles_pdf")
                if has_mask_rects or has_mask_circles:
                    continue

                start_pos = detect_item.get("start", {})
                end_pos = detect_item.get("end", {})
                entity_type = detect_item.get("entity", "PII")
                normalized_entity_type = _normalize_entity_key(entity_type) or "PII"

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
                                line_rects_items.append(
                                    {
                                        "rect": {"x0": r[0], "y0": r[1], "x1": r[2], "y1": r[3]},
                                        "page_num": p,
                                    }
                                )
                    except Exception:
                        line_rects_items = []

                if line_rects_items:
                    for item in line_rects_items:
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

                        target_page_num = int(item.get("page_num", page_num))
                        target_rect = [x0, y0, x1, y1]
                        if _is_mask_covered(target_page_num, target_rect):
                            continue

                        redactions.append(
                            {
                                "page_num": target_page_num,
                                "rect": target_rect,
                                "entity_type": normalized_entity_type,
                            }
                        )

        # 同一矩形の重複追加を除去
        unique_redactions: List[Dict[str, Any]] = []
        seen_redactions = set()
        for item in redactions:
            try:
                page_num = int(item.get("page_num", 0))
                x0, y0, x1, y1 = map(float, item.get("rect", [])[:4])
                entity_type = str(item.get("entity_type", "PII") or "PII")
            except Exception:
                continue
            key = (
                page_num,
                round(x0, 3),
                round(y0, 3),
                round(x1, 3),
                round(y1, 3),
                entity_type,
            )
            if key in seen_redactions:
                continue
            seen_redactions.add(key)
            unique_redactions.append(
                {"page_num": page_num, "rect": [x0, y0, x1, y1], "entity_type": entity_type}
            )
        redactions = unique_redactions
        unique_circles: List[Dict[str, Any]] = []
        seen_circles = set()
        for item in circle_masks:
            try:
                page_num = int(item.get("page_num", 0))
                center_x = float(item.get("center_x"))
                center_y = float(item.get("center_y"))
                radius = float(item.get("radius"))
                entity_type = str(item.get("entity_type", "PII") or "PII")
            except Exception:
                continue
            if radius <= 0.0:
                continue
            key = (
                page_num,
                round(center_x, 3),
                round(center_y, 3),
                round(radius, 3),
                entity_type,
            )
            if key in seen_circles:
                continue
            seen_circles.add(key)
            unique_circles.append(
                {
                    "page_num": page_num,
                    "center_x": center_x,
                    "center_y": center_y,
                    "radius": radius,
                    "entity_type": entity_type,
                }
            )
        circle_masks = unique_circles

        # PDFに黒塗りを適用
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with fitz.open(str(pdf_path)) as out_doc:
            redaction_count = 0

            # ページ単位でredactionを追加・適用
            redactions_by_page: Dict[int, List[Dict[str, Any]]] = {}
            for item in redactions:
                redactions_by_page.setdefault(int(item["page_num"]), []).append(item)
            circles_by_page: Dict[int, List[Dict[str, Any]]] = {}
            for item in circle_masks:
                circles_by_page.setdefault(int(item["page_num"]), []).append(item)

            target_pages = sorted(set(redactions_by_page.keys()) | set(circles_by_page.keys()))
            for page_num in target_pages:
                if page_num < 0 or page_num >= len(out_doc):
                    continue
                page = out_doc[page_num]
                page_redactions = redactions_by_page.get(page_num, [])
                page_circles = circles_by_page.get(page_num, [])

                for item in page_redactions:
                    rect = fitz.Rect(item["rect"]) & page.rect
                    if (not rect) or rect.width <= 0 or rect.height <= 0:
                        continue

                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    redaction_count += 1

                # 追加したredactionをこのページへ反映
                if page_redactions:
                    page.apply_redactions()

                for circle in page_circles:
                    try:
                        center_x = float(circle["center_x"])
                        center_y = float(circle["center_y"])
                        radius = float(circle["radius"])
                    except Exception:
                        continue
                    if radius <= 0.0:
                        continue

                    circle_rect = fitz.Rect(
                        center_x - radius,
                        center_y - radius,
                        center_x + radius,
                        center_y + radius,
                    )
                    if not (circle_rect & page.rect):
                        continue

                    shape = page.new_shape()
                    shape.draw_circle((center_x, center_y), radius)
                    shape.finish(color=(0, 0, 0), fill=(0, 0, 0), width=0)
                    shape.commit(overlay=True)
                    redaction_count += 1

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

    @staticmethod
    def run_export_annotations(
        detect_result: Dict[str, Any],
        pdf_path: Path,
        output_path: Path,
    ) -> Dict[str, Any]:
        """検出結果をPDF注釈として保存する"""
        logger.info(f"run_export_annotations開始: {pdf_path} → {output_path}")

        import fitz
        from src.pdf.pdf_locator import PDFTextLocator

        if not isinstance(detect_result, dict):
            logger.error(f"detect_resultが辞書型ではありません: {type(detect_result)}")
            raise TypeError("detect_resultは辞書型である必要があります")

        if not Path(pdf_path).exists():
            logger.error(f"入力PDFファイルが見つかりません: {pdf_path}")
            raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")

        detect_list = detect_result.get("detect", [])
        if not isinstance(detect_list, list):
            detect_list = []

        offset2coords_map = detect_result.get("offset2coordsMap", {})
        text_2d = detect_result.get("text", [])

        block_start_global: Dict[Tuple[int, int], int] = {}
        global_cursor = 0
        if isinstance(text_2d, list):
            for page_num, page_blocks in enumerate(text_2d):
                if not isinstance(page_blocks, list):
                    continue
                for block_num, block_text in enumerate(page_blocks):
                    text = str(block_text or "")
                    block_start_global[(page_num, block_num)] = global_cursor
                    global_cursor += len(text)

        def _normalize_rect(rect: Any) -> Optional[List[float]]:
            if not isinstance(rect, (list, tuple)) or len(rect) < 4:
                return None
            try:
                x0, y0, x1, y1 = map(float, rect[:4])
            except Exception:
                return None
            if x1 <= x0 or y1 <= y0:
                return None
            return [x0, y0, x1, y1]

        def _group_rects_by_line(rects: List[List[float]], y_threshold: float = 2.0) -> List[List[float]]:
            if not rects:
                return []
            items = []
            for rect in rects:
                try:
                    x0, y0, x1, y1 = map(float, rect[:4])
                except Exception:
                    continue
                cy = (y0 + y1) / 2.0
                items.append((cy, [x0, y0, x1, y1]))

            items.sort(key=lambda item: item[0])
            groups: List[List[List[float]]] = []
            for cy, rect in items:
                if not groups:
                    groups.append([rect])
                    continue
                group = groups[-1]
                group_cy = sum(((r[1] + r[3]) / 2.0) for r in group) / len(group)
                if abs(cy - group_cy) <= y_threshold:
                    group.append(rect)
                else:
                    groups.append([rect])

            merged = []
            for group in groups:
                merged.append(
                    [
                        min(r[0] for r in group),
                        min(r[1] for r in group),
                        max(r[2] for r in group),
                        max(r[3] for r in group),
                    ]
                )
            return merged

        def _default_page_num(entity: Dict[str, Any]) -> int:
            start_pos = entity.get("start", {})
            if isinstance(start_pos, dict):
                try:
                    return int(start_pos.get("page_num", 0) or 0)
                except Exception:
                    return 0
            try:
                return int(entity.get("page_num", 0) or 0)
            except Exception:
                return 0

        def _dedupe_rect_items(items: List[Tuple[int, List[float]]]) -> List[Tuple[int, List[float]]]:
            unique_items: List[Tuple[int, List[float]]] = []
            seen = set()
            for page_num, rect in items:
                key = (
                    int(page_num),
                    round(rect[0], 3),
                    round(rect[1], 3),
                    round(rect[2], 3),
                    round(rect[3], 3),
                )
                if key in seen:
                    continue
                seen.add(key)
                unique_items.append((int(page_num), rect))
            return unique_items

        def _resolve_shape_rects(entity: Dict[str, Any]) -> List[Tuple[int, List[float]]]:
            rect_items: List[Tuple[int, List[float]]] = []
            default_page_num = _default_page_num(entity)

            raw_mask_rects = entity.get("mask_rects_pdf")
            if isinstance(raw_mask_rects, list):
                for raw_rect in raw_mask_rects:
                    rect_page_num = default_page_num
                    rect_source = raw_rect
                    if isinstance(raw_rect, dict):
                        try:
                            rect_page_num = int(raw_rect.get("page_num", rect_page_num) or rect_page_num)
                        except Exception:
                            rect_page_num = default_page_num
                        if "rect" in raw_rect:
                            rect_source = raw_rect.get("rect")
                        else:
                            rect_source = [
                                raw_rect.get("x0"),
                                raw_rect.get("y0"),
                                raw_rect.get("x1"),
                                raw_rect.get("y1"),
                            ]
                    normalized_rect = _normalize_rect(rect_source)
                    if not normalized_rect:
                        continue
                    rect_items.append((rect_page_num, normalized_rect))

            raw_mask_circles = entity.get("mask_circles_pdf")
            if isinstance(raw_mask_circles, list):
                for raw_circle in raw_mask_circles:
                    circle_page_num = default_page_num
                    center_x = None
                    center_y = None
                    radius = None

                    if isinstance(raw_circle, dict):
                        try:
                            circle_page_num = int(
                                raw_circle.get("page_num", circle_page_num) or circle_page_num
                            )
                        except Exception:
                            circle_page_num = default_page_num
                        center = raw_circle.get("center")
                        if isinstance(center, (list, tuple)) and len(center) >= 2:
                            try:
                                center_x = float(center[0])
                                center_y = float(center[1])
                            except Exception:
                                center_x = None
                                center_y = None
                        if center_x is None or center_y is None:
                            try:
                                center_x = float(raw_circle.get("center_x"))
                                center_y = float(raw_circle.get("center_y"))
                            except Exception:
                                center_x = None
                                center_y = None
                        try:
                            radius = float(raw_circle.get("radius"))
                        except Exception:
                            radius = None
                    elif isinstance(raw_circle, (list, tuple)) and len(raw_circle) >= 3:
                        try:
                            center_x = float(raw_circle[0])
                            center_y = float(raw_circle[1])
                            radius = float(raw_circle[2])
                        except Exception:
                            center_x = None
                            center_y = None
                            radius = None

                    if center_x is None or center_y is None or radius is None or radius <= 0.0:
                        continue
                    rect_items.append(
                        (
                            circle_page_num,
                            [
                                center_x - radius,
                                center_y - radius,
                                center_x + radius,
                                center_y + radius,
                            ],
                        )
                    )

            return _dedupe_rect_items(rect_items)

        def _resolve_text_rects(
            entity: Dict[str, Any],
            locator: "PDFTextLocator",
        ) -> List[Tuple[int, List[float]]]:
            rect_items: List[Tuple[int, List[float]]] = []
            default_page_num = _default_page_num(entity)

            raw_rects = entity.get("rects_pdf")
            if isinstance(raw_rects, list):
                for raw_rect in raw_rects:
                    rect_page_num = default_page_num
                    rect_source = raw_rect
                    if isinstance(raw_rect, dict):
                        try:
                            rect_page_num = int(raw_rect.get("page_num", rect_page_num) or rect_page_num)
                        except Exception:
                            rect_page_num = default_page_num
                        if "rect" in raw_rect:
                            rect_source = raw_rect.get("rect")
                        else:
                            rect_source = [
                                raw_rect.get("x0"),
                                raw_rect.get("y0"),
                                raw_rect.get("x1"),
                                raw_rect.get("y1"),
                            ]
                    normalized_rect = _normalize_rect(rect_source)
                    if not normalized_rect:
                        continue
                    rect_items.append((rect_page_num, normalized_rect))
            if rect_items:
                return _dedupe_rect_items(rect_items)

            start_pos = entity.get("start", {})
            end_pos = entity.get("end", {})
            if not isinstance(start_pos, dict) or not isinstance(end_pos, dict):
                return []

            page_num = int(start_pos.get("page_num", 0) or 0)
            block_num = int(start_pos.get("block_num", 0) or 0)
            start_offset = int(start_pos.get("offset", 0) or 0)
            end_page_num = int(end_pos.get("page_num", page_num) or page_num)
            end_block_num = int(end_pos.get("block_num", block_num) or block_num)
            end_offset = int(end_pos.get("offset", start_offset) or start_offset)

            line_rects_items: List[Dict[str, Any]] = []
            try:
                key_s = (page_num, block_num)
                key_e = (end_page_num, end_block_num)
                if key_s in block_start_global and key_e in block_start_global:
                    start_global = block_start_global[key_s] + start_offset
                    end_global_excl = block_start_global[key_e] + end_offset + 1
                    line_rects_items = locator.get_pii_line_rects(start_global, end_global_excl)
            except Exception:
                line_rects_items = []

            if line_rects_items:
                for item in line_rects_items:
                    rect_info = item.get("rect", {})
                    normalized_rect = _normalize_rect(
                        [
                            rect_info.get("x0"),
                            rect_info.get("y0"),
                            rect_info.get("x1"),
                            rect_info.get("y1"),
                        ]
                    )
                    if not normalized_rect:
                        continue
                    target_page_num = int(item.get("page_num", page_num))
                    rect_items.append((target_page_num, normalized_rect))
                return _dedupe_rect_items(rect_items)

            if not isinstance(offset2coords_map, dict):
                return []

            page_rects: Dict[int, List[List[float]]] = {}
            try:
                for p in range(page_num, end_page_num + 1):
                    page_dict = offset2coords_map.get(str(p), {})
                    if not isinstance(page_dict, dict) or not page_dict:
                        continue
                    block_ids = sorted([int(k) for k in page_dict.keys() if str(k).isdigit()])
                    if not block_ids:
                        continue
                    b_start = block_num if p == page_num else block_ids[0]
                    b_end = end_block_num if p == end_page_num else block_ids[-1]
                    for b in block_ids:
                        if b < b_start or b > b_end:
                            continue
                        block_list = page_dict.get(str(b), [])
                        if not isinstance(block_list, list) or not block_list:
                            continue
                        o_start = start_offset if (p == page_num and b == block_num) else 0
                        o_end = end_offset if (p == end_page_num and b == end_block_num) else (len(block_list) - 1)
                        if o_start > o_end:
                            continue
                        for off in range(o_start, o_end + 1):
                            bbox = block_list[off] if 0 <= off < len(block_list) else None
                            normalized_rect = _normalize_rect(bbox)
                            if not normalized_rect:
                                continue
                            page_rects.setdefault(p, []).append(normalized_rect)
            except Exception:
                return []

            for p, rects in page_rects.items():
                for rect in _group_rects_by_line(rects):
                    rect_items.append((p, rect))

            return _dedupe_rect_items(rect_items)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_save_path: Optional[Path] = None
        try:
            if output_path.resolve() == Path(pdf_path).resolve():
                temp_save_path = output_path.with_suffix(output_path.suffix + ".tmp")
        except Exception:
            temp_save_path = None
        annotation_count = 0

        with fitz.open(str(pdf_path)) as doc:
            locator = PDFTextLocator(doc)

            for detect_item in detect_list:
                if not isinstance(detect_item, dict):
                    continue

                entity_type = str(detect_item.get("entity", "PII") or "PII")
                origin = str(detect_item.get("origin", "") or "")
                word = str(detect_item.get("word", "") or "")
                title_text = entity_type
                content_text = f"origin={origin}, entity={entity_type}, word={word}"

                shape_rects = _resolve_shape_rects(detect_item)
                if shape_rects:
                    for page_num, rect in shape_rects:
                        if page_num < 0 or page_num >= len(doc):
                            continue
                        page = doc[page_num]
                        fitz_rect = fitz.Rect(rect) & page.rect
                        if (not fitz_rect) or fitz_rect.width <= 0 or fitz_rect.height <= 0:
                            continue
                        annot = page.add_rect_annot(fitz_rect)
                        info = annot.info
                        info["title"] = title_text
                        info["content"] = content_text
                        info["subject"] = entity_type
                        annot.set_info(info)
                        annot.update()
                        annotation_count += 1
                    continue

                text_rects = _resolve_text_rects(detect_item, locator)
                for page_num, rect in text_rects:
                    if page_num < 0 or page_num >= len(doc):
                        continue
                    page = doc[page_num]
                    fitz_rect = fitz.Rect(rect) & page.rect
                    if (not fitz_rect) or fitz_rect.width <= 0 or fitz_rect.height <= 0:
                        continue
                    annot = page.add_highlight_annot(fitz_rect)
                    info = annot.info
                    info["title"] = title_text
                    info["content"] = content_text
                    info["subject"] = entity_type
                    annot.set_info(info)
                    annot.update()
                    annotation_count += 1

            save_path = temp_save_path or output_path
            doc.save(str(save_path), garbage=4, deflate=True, clean=True)

        if temp_save_path and temp_save_path.exists():
            temp_save_path.replace(output_path)

        logger.info(f"run_export_annotations完了: {annotation_count} 件の注釈を追加")
        return {
            "output_path": str(output_path),
            "annotation_count": annotation_count,
            "success": True,
        }

    @staticmethod
    def run_mask_as_image(
        detect_result: Dict[str, Any],
        pdf_path: Path,
        output_path: Path,
        mask_styles: Optional[Dict[str, Dict[str, float]]] = None,
        dpi: int = 300,
    ) -> Dict[str, Any]:
        """通常マスク後に各ページを画像化し、画像のみPDFとして保存する"""
        logger.info(f"run_mask_as_image開始: {pdf_path} → {output_path}, dpi={dpi}")

        import os
        import tempfile
        import fitz

        if not isinstance(detect_result, dict):
            logger.error(f"detect_resultが辞書型ではありません: {type(detect_result)}")
            raise TypeError("detect_resultは辞書型である必要があります")

        if not Path(pdf_path).exists():
            logger.error(f"入力PDFファイルが見つかりません: {pdf_path}")
            raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")
        try:
            dpi = int(dpi)
        except (TypeError, ValueError) as exc:
            raise ValueError("dpiは整数で指定してください") from exc
        if dpi <= 0:
            raise ValueError("dpiは1以上で指定してください")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        temp_mask_fd, temp_mask_name = tempfile.mkstemp(
            suffix=".pdf",
            dir=str(output_path.parent),
        )
        os.close(temp_mask_fd)
        temp_mask_path = Path(temp_mask_name)

        try:
            mask_result = PipelineService.run_mask(
                detect_result=detect_result,
                pdf_path=Path(pdf_path),
                output_path=temp_mask_path,
                mask_styles=mask_styles,
            )

            with fitz.open(str(temp_mask_path)) as masked_doc:
                with fitz.open() as image_pdf:
                    for page in masked_doc:
                        pix = page.get_pixmap(dpi=dpi, alpha=False)
                        image_page = image_pdf.new_page(
                            width=page.rect.width,
                            height=page.rect.height,
                        )
                        image_page.insert_image(image_page.rect, pixmap=pix)
                    image_pdf.save(str(output_path), garbage=4, deflate=True, clean=True)

            entity_count = int(mask_result.get("entity_count", 0))
            logger.info(f"run_mask_as_image完了: {entity_count} 件を画像PDF化")
            return {
                "output_path": str(output_path),
                "entity_count": entity_count,
                "success": True,
            }
        finally:
            try:
                if temp_mask_path.exists():
                    temp_mask_path.unlink()
            except Exception:
                logger.warning(f"一時ファイル削除に失敗: {temp_mask_path}")

    @staticmethod
    def run_export_marked_as_image(
        detect_result: Dict[str, Any],
        pdf_path: Path,
        output_path: Path,
        dpi: int = 300,
        mark_styles: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, Any]:
        """検出項目のマークを半透明で重ね、画像のみPDFとして保存する"""
        logger.info(f"run_export_marked_as_image開始: {pdf_path} → {output_path}, dpi={dpi}")

        import fitz
        from src.pdf.pdf_locator import PDFTextLocator

        if not isinstance(detect_result, dict):
            logger.error(f"detect_resultが辞書型ではありません: {type(detect_result)}")
            raise TypeError("detect_resultは辞書型である必要があります")

        if not Path(pdf_path).exists():
            logger.error(f"入力PDFファイルが見つかりません: {pdf_path}")
            raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")
        try:
            dpi = int(dpi)
        except (TypeError, ValueError) as exc:
            raise ValueError("dpiは整数で指定してください") from exc
        if dpi <= 0:
            raise ValueError("dpiは1以上で指定してください")

        detect_list = detect_result.get("detect", [])
        if not isinstance(detect_list, list):
            detect_list = []
        offset2coords_map = detect_result.get("offset2coordsMap", {})
        text_2d = detect_result.get("text", [])

        block_start_global: Dict[Tuple[int, int], int] = {}
        global_cursor = 0
        if isinstance(text_2d, list):
            for page_num, page_blocks in enumerate(text_2d):
                if not isinstance(page_blocks, list):
                    continue
                for block_num, block_text in enumerate(page_blocks):
                    text = str(block_text or "")
                    block_start_global[(page_num, block_num)] = global_cursor
                    global_cursor += len(text)

        def _normalize_entity_key(name: str) -> str:
            normalized = str(name or "").strip()
            if not normalized:
                return "OTHER"
            if normalized.lower() == "address":
                return "LOCATION"
            return normalized.upper()

        def _normalize_rect(rect: Any) -> Optional[List[float]]:
            if not isinstance(rect, (list, tuple)) or len(rect) < 4:
                return None
            try:
                x0, y0, x1, y1 = map(float, rect[:4])
            except Exception:
                return None
            if x1 <= x0 or y1 <= y0:
                return None
            return [x0, y0, x1, y1]

        def _group_rects_by_line(rects: List[List[float]], y_threshold: float = 2.0) -> List[List[float]]:
            if not rects:
                return []
            items = []
            for rect in rects:
                try:
                    x0, y0, x1, y1 = map(float, rect[:4])
                except Exception:
                    continue
                cy = (y0 + y1) / 2.0
                items.append((cy, [x0, y0, x1, y1]))

            items.sort(key=lambda item: item[0])
            groups: List[List[List[float]]] = []
            for cy, rect in items:
                if not groups:
                    groups.append([rect])
                    continue
                group = groups[-1]
                group_cy = sum(((r[1] + r[3]) / 2.0) for r in group) / len(group)
                if abs(cy - group_cy) <= y_threshold:
                    group.append(rect)
                else:
                    groups.append([rect])

            merged = []
            for group in groups:
                merged.append(
                    [
                        min(r[0] for r in group),
                        min(r[1] for r in group),
                        max(r[2] for r in group),
                        max(r[3] for r in group),
                    ]
                )
            return merged

        def _default_page_num(entity: Dict[str, Any]) -> int:
            start_pos = entity.get("start", {})
            if isinstance(start_pos, dict):
                try:
                    return int(start_pos.get("page_num", 0) or 0)
                except Exception:
                    return 0
            try:
                return int(entity.get("page_num", 0) or 0)
            except Exception:
                return 0

        def _dedupe_rect_items(items: List[Tuple[int, List[float]]]) -> List[Tuple[int, List[float]]]:
            unique_items: List[Tuple[int, List[float]]] = []
            seen = set()
            for page_num, rect in items:
                key = (
                    int(page_num),
                    round(rect[0], 3),
                    round(rect[1], 3),
                    round(rect[2], 3),
                    round(rect[3], 3),
                )
                if key in seen:
                    continue
                seen.add(key)
                unique_items.append((int(page_num), rect))
            return unique_items

        def _normalize_circle(circle: Any, default_page_num: int) -> Optional[Tuple[int, float, float, float]]:
            page_num = int(default_page_num)
            center_x = None
            center_y = None
            radius = None

            if isinstance(circle, dict):
                try:
                    page_num = int(circle.get("page_num", page_num) or page_num)
                except Exception:
                    page_num = int(default_page_num)
                center = circle.get("center")
                if isinstance(center, (list, tuple)) and len(center) >= 2:
                    try:
                        center_x = float(center[0])
                        center_y = float(center[1])
                    except Exception:
                        center_x = None
                        center_y = None
                if center_x is None or center_y is None:
                    try:
                        center_x = float(circle.get("center_x"))
                        center_y = float(circle.get("center_y"))
                    except Exception:
                        center_x = None
                        center_y = None
                try:
                    radius = float(circle.get("radius"))
                except Exception:
                    radius = None
            elif isinstance(circle, (list, tuple)) and len(circle) >= 3:
                try:
                    center_x = float(circle[0])
                    center_y = float(circle[1])
                    radius = float(circle[2])
                except Exception:
                    center_x = None
                    center_y = None
                    radius = None

            if center_x is None or center_y is None or radius is None or radius <= 0.0:
                return None
            return int(page_num), float(center_x), float(center_y), float(radius)

        def _resolve_shape_geometries(
            entity: Dict[str, Any],
        ) -> Tuple[List[Tuple[int, List[float]]], List[Tuple[int, float, float, float]]]:
            rect_items: List[Tuple[int, List[float]]] = []
            circle_items: List[Tuple[int, float, float, float]] = []
            default_page_num = _default_page_num(entity)
            selection_mode = str(entity.get("selection_mode", "") or "").lower()

            has_circle_masks = False
            raw_mask_circles = entity.get("mask_circles_pdf")
            if isinstance(raw_mask_circles, list):
                for raw_circle in raw_mask_circles:
                    normalized_circle = _normalize_circle(raw_circle, default_page_num)
                    if not normalized_circle:
                        continue
                    has_circle_masks = True
                    circle_items.append(normalized_circle)

            raw_mask_rects = entity.get("mask_rects_pdf")
            if isinstance(raw_mask_rects, list):
                if not (selection_mode == "circle_drag" and has_circle_masks):
                    for raw_rect in raw_mask_rects:
                        rect_page_num = default_page_num
                        rect_source = raw_rect
                        if isinstance(raw_rect, dict):
                            try:
                                rect_page_num = int(
                                    raw_rect.get("page_num", rect_page_num) or rect_page_num
                                )
                            except Exception:
                                rect_page_num = default_page_num
                            if "rect" in raw_rect:
                                rect_source = raw_rect.get("rect")
                            else:
                                rect_source = [
                                    raw_rect.get("x0"),
                                    raw_rect.get("y0"),
                                    raw_rect.get("x1"),
                                    raw_rect.get("y1"),
                                ]

                        normalized_rect = _normalize_rect(rect_source)
                        if not normalized_rect:
                            continue
                        rect_items.append((rect_page_num, normalized_rect))

            unique_rects = _dedupe_rect_items(rect_items)

            unique_circles: List[Tuple[int, float, float, float]] = []
            seen_circles = set()
            for page_num, center_x, center_y, radius in circle_items:
                key = (
                    int(page_num),
                    round(center_x, 3),
                    round(center_y, 3),
                    round(radius, 3),
                )
                if key in seen_circles:
                    continue
                seen_circles.add(key)
                unique_circles.append((int(page_num), center_x, center_y, radius))

            return unique_rects, unique_circles

        def _resolve_text_rects(
            entity: Dict[str, Any],
            locator: "PDFTextLocator",
        ) -> List[Tuple[int, List[float]]]:
            rect_items: List[Tuple[int, List[float]]] = []
            default_page_num = _default_page_num(entity)

            raw_rects = entity.get("rects_pdf")
            if isinstance(raw_rects, list):
                for raw_rect in raw_rects:
                    rect_page_num = default_page_num
                    rect_source = raw_rect
                    if isinstance(raw_rect, dict):
                        try:
                            rect_page_num = int(raw_rect.get("page_num", rect_page_num) or rect_page_num)
                        except Exception:
                            rect_page_num = default_page_num
                        if "rect" in raw_rect:
                            rect_source = raw_rect.get("rect")
                        else:
                            rect_source = [
                                raw_rect.get("x0"),
                                raw_rect.get("y0"),
                                raw_rect.get("x1"),
                                raw_rect.get("y1"),
                            ]
                    normalized_rect = _normalize_rect(rect_source)
                    if not normalized_rect:
                        continue
                    rect_items.append((rect_page_num, normalized_rect))
            if rect_items:
                return _dedupe_rect_items(rect_items)

            start_pos = entity.get("start", {})
            end_pos = entity.get("end", {})
            if not isinstance(start_pos, dict) or not isinstance(end_pos, dict):
                return []

            page_num = int(start_pos.get("page_num", 0) or 0)
            block_num = int(start_pos.get("block_num", 0) or 0)
            start_offset = int(start_pos.get("offset", 0) or 0)
            end_page_num = int(end_pos.get("page_num", page_num) or page_num)
            end_block_num = int(end_pos.get("block_num", block_num) or block_num)
            end_offset = int(end_pos.get("offset", start_offset) or start_offset)

            line_rects_items: List[Dict[str, Any]] = []
            try:
                key_s = (page_num, block_num)
                key_e = (end_page_num, end_block_num)
                if key_s in block_start_global and key_e in block_start_global:
                    start_global = block_start_global[key_s] + start_offset
                    end_global_excl = block_start_global[key_e] + end_offset + 1
                    line_rects_items = locator.get_pii_line_rects(start_global, end_global_excl)
            except Exception:
                line_rects_items = []

            if line_rects_items:
                for item in line_rects_items:
                    rect_info = item.get("rect", {})
                    normalized_rect = _normalize_rect(
                        [
                            rect_info.get("x0"),
                            rect_info.get("y0"),
                            rect_info.get("x1"),
                            rect_info.get("y1"),
                        ]
                    )
                    if not normalized_rect:
                        continue
                    target_page_num = int(item.get("page_num", page_num))
                    rect_items.append((target_page_num, normalized_rect))
                return _dedupe_rect_items(rect_items)

            if not isinstance(offset2coords_map, dict):
                return []

            page_rects: Dict[int, List[List[float]]] = {}
            try:
                for p in range(page_num, end_page_num + 1):
                    page_dict = offset2coords_map.get(str(p), {})
                    if not isinstance(page_dict, dict) or not page_dict:
                        continue
                    block_ids = sorted([int(k) for k in page_dict.keys() if str(k).isdigit()])
                    if not block_ids:
                        continue
                    b_start = block_num if p == page_num else block_ids[0]
                    b_end = end_block_num if p == end_page_num else block_ids[-1]
                    for b in block_ids:
                        if b < b_start or b > b_end:
                            continue
                        block_list = page_dict.get(str(b), [])
                        if not isinstance(block_list, list) or not block_list:
                            continue
                        o_start = start_offset if (p == page_num and b == block_num) else 0
                        o_end = end_offset if (p == end_page_num and b == end_block_num) else (len(block_list) - 1)
                        if o_start > o_end:
                            continue
                        for off in range(o_start, o_end + 1):
                            bbox = block_list[off] if 0 <= off < len(block_list) else None
                            normalized_rect = _normalize_rect(bbox)
                            if not normalized_rect:
                                continue
                            page_rects.setdefault(p, []).append(normalized_rect)
            except Exception:
                return []

            for p, rects in page_rects.items():
                for rect in _group_rects_by_line(rects):
                    rect_items.append((p, rect))
            return _dedupe_rect_items(rect_items)

        def _resolve_mark_style(entity_type: str) -> Tuple[float, float, float, float]:
            normalized_entity = _normalize_entity_key(entity_type)
            default_styles: Dict[str, Dict[str, float]] = {
                "PERSON": {"r": 1.0, "g": 0.78, "b": 0.78, "a": 0.35},
                "LOCATION": {"r": 0.78, "g": 1.0, "b": 0.78, "a": 0.35},
                "PHONE_NUMBER": {"r": 0.78, "g": 0.78, "b": 1.0, "a": 0.35},
                "DATE_TIME": {"r": 1.0, "g": 1.0, "b": 0.78, "a": 0.35},
                "INDIVIDUAL_NUMBER": {"r": 1.0, "g": 0.78, "b": 1.0, "a": 0.35},
                "YEAR": {"r": 0.78, "g": 1.0, "b": 1.0, "a": 0.35},
                "PROPER_NOUN": {"r": 1.0, "g": 0.86, "b": 0.70, "a": 0.35},
                "OTHER": {"r": 0.78, "g": 0.78, "b": 0.78, "a": 0.35},
            }
            style = default_styles.get(normalized_entity, default_styles["OTHER"]).copy()
            custom_style = (mark_styles or {}).get(normalized_entity)
            if isinstance(custom_style, dict):
                for key in ["r", "g", "b", "a"]:
                    value = custom_style.get(key)
                    if value is None:
                        continue
                    try:
                        style[key] = float(value)
                    except (TypeError, ValueError):
                        continue
            style["r"] = min(1.0, max(0.0, style["r"]))
            style["g"] = min(1.0, max(0.0, style["g"]))
            style["b"] = min(1.0, max(0.0, style["b"]))
            style["a"] = min(1.0, max(0.0, style["a"]))
            return style["r"], style["g"], style["b"], style["a"]

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        marked_count = 0
        with fitz.open(str(pdf_path)) as doc:
            locator = PDFTextLocator(doc)

            for detect_item in detect_list:
                if not isinstance(detect_item, dict):
                    continue
                entity_type = str(detect_item.get("entity", "PII") or "PII")

                shape_rects, shape_circles = _resolve_shape_geometries(detect_item)
                if shape_rects or shape_circles:
                    for page_num, rect in shape_rects:
                        if page_num < 0 or page_num >= len(doc):
                            continue
                        page = doc[page_num]
                        fitz_rect = fitz.Rect(rect) & page.rect
                        if (not fitz_rect) or fitz_rect.width <= 0 or fitz_rect.height <= 0:
                            continue
                        r, g, b, a = _resolve_mark_style(entity_type)
                        shape = page.new_shape()
                        shape.draw_rect(fitz_rect)
                        shape.finish(
                            color=(r, g, b),
                            fill=(r, g, b),
                            width=0,
                            fill_opacity=a,
                            stroke_opacity=a,
                        )
                        shape.commit(overlay=True)
                        marked_count += 1

                    for page_num, center_x, center_y, radius in shape_circles:
                        if page_num < 0 or page_num >= len(doc):
                            continue
                        if radius <= 0.0:
                            continue
                        page = doc[page_num]
                        circle_rect = fitz.Rect(
                            center_x - radius,
                            center_y - radius,
                            center_x + radius,
                            center_y + radius,
                        )
                        if not (circle_rect & page.rect):
                            continue
                        r, g, b, a = _resolve_mark_style(entity_type)
                        shape = page.new_shape()
                        shape.draw_circle((center_x, center_y), radius)
                        shape.finish(
                            color=(r, g, b),
                            fill=(r, g, b),
                            width=0,
                            fill_opacity=a,
                            stroke_opacity=a,
                        )
                        shape.commit(overlay=True)
                        marked_count += 1
                    continue

                text_rects = _resolve_text_rects(detect_item, locator)
                for page_num, rect in text_rects:
                    if page_num < 0 or page_num >= len(doc):
                        continue
                    page = doc[page_num]
                    fitz_rect = fitz.Rect(rect) & page.rect
                    if (not fitz_rect) or fitz_rect.width <= 0 or fitz_rect.height <= 0:
                        continue
                    r, g, b, a = _resolve_mark_style(entity_type)
                    shape = page.new_shape()
                    shape.draw_rect(fitz_rect)
                    shape.finish(
                        color=(r, g, b),
                        fill=(r, g, b),
                        width=0,
                        fill_opacity=a,
                        stroke_opacity=a,
                    )
                    shape.commit(overlay=True)
                    marked_count += 1

            with fitz.open() as image_pdf:
                for page in doc:
                    pix = page.get_pixmap(dpi=dpi, alpha=False)
                    image_page = image_pdf.new_page(
                        width=page.rect.width,
                        height=page.rect.height,
                    )
                    image_page.insert_image(image_page.rect, pixmap=pix)
                image_pdf.save(str(output_path), garbage=4, deflate=True, clean=True)

        logger.info(f"run_export_marked_as_image完了: {marked_count} 件を画像PDF化")
        return {
            "output_path": str(output_path),
            "entity_count": marked_count,
            "success": True,
        }
