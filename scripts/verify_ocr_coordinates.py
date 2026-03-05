"""
座標ずれ検証スクリプト。

使い方:
    python scripts/verify_ocr_coordinates.py a1.pdf a1_image.pdf [--dpi 300]

処理フロー:
    1. a1.pdf → rawdictからspan単位の(text, bbox, color)を取得(ground truth)
    2. a1_image.pdf → NDLOCRServiceでOCR実行
    3. テキスト正規化マッチングでペア構築
    4. マッチしたペアの座標差分(dx, dy)を算出
    5. 平均offset・標準偏差をレポート
"""

from __future__ import annotations

import argparse
import statistics
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _normalize_text(text: str) -> str:
    """NFKC正規化 + 空白除去"""
    return unicodedata.normalize("NFKC", text).replace(" ", "").replace("\u3000", "")


def extract_ground_truth(pdf_path: Path) -> List[Dict]:
    """rawdictからspan単位のテキスト・bbox・colorを取得する。"""
    import fitz

    results = []
    with fitz.open(str(pdf_path)) as doc:
        for page_num, page in enumerate(doc):
            # rawdict: span.text は空のため chars から組み立て
            text_dict = page.get_text("rawdict") or {}
            for block in text_dict.get("blocks", []):
                if not isinstance(block, dict) or block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        chars = span.get("chars", [])
                        if chars:
                            text = "".join(c.get("c", "") for c in chars).strip()
                        else:
                            text = str(span.get("text", "") or "").strip()
                        if not text:
                            continue
                        bbox = span.get("bbox")
                        if not bbox or len(bbox) < 4:
                            continue
                        results.append({
                            "text": text,
                            "norm_text": _normalize_text(text),
                            "bbox": tuple(bbox[:4]),
                            "color": span.get("color"),
                            "page_num": page_num,
                        })
    return results


def run_ocr(pdf_path: Path, dpi: int = 300) -> List[Dict]:
    """NDLOCRServiceでOCRを実行して結果を返す。"""
    from src.ocr.ndlocr_service import NDLOCRService

    service = NDLOCRService()
    ocr_by_page = service.run_ocr_on_pdf(pdf_path, dpi=dpi)
    results = []
    for page_num, page_results in ocr_by_page.items():
        for r in page_results:
            results.append({
                "text": r.text,
                "norm_text": _normalize_text(r.text),
                "x": r.x,
                "y": r.y,
                "width": r.width,
                "height": r.height,
                "page_num": page_num,
            })
    return results


def match_pairs(
    ground_truth: List[Dict],
    ocr_results: List[Dict],
) -> List[Tuple[Dict, Dict]]:
    """テキスト正規化マッチングでペアを構築する。"""
    pairs = []
    used_gt = set()

    for ocr in ocr_results:
        ocr_norm = ocr["norm_text"]
        if not ocr_norm:
            continue
        best: Optional[int] = None
        for i, gt in enumerate(ground_truth):
            if i in used_gt:
                continue
            if gt["page_num"] != ocr["page_num"]:
                continue
            gt_norm = gt["norm_text"]
            if ocr_norm == gt_norm or ocr_norm in gt_norm or gt_norm in ocr_norm:
                best = i
                break
        if best is not None:
            used_gt.add(best)
            pairs.append((ground_truth[best], ocr))

    return pairs


def compute_offsets(
    pairs: List[Tuple[Dict, Dict]],
) -> Tuple[List[float], List[float]]:
    """各ペアの座標差分(dx, dy)を算出する。"""
    dx_list: List[float] = []
    dy_list: List[float] = []
    for gt, ocr in pairs:
        gt_x0, gt_y0, gt_x1, gt_y1 = gt["bbox"]
        ocr_cx = ocr["x"] + ocr["width"] / 2
        ocr_cy = ocr["y"] + ocr["height"] / 2
        gt_cx = (gt_x0 + gt_x1) / 2
        gt_cy = (gt_y0 + gt_y1) / 2
        dx_list.append(ocr_cx - gt_cx)
        dy_list.append(ocr_cy - gt_cy)
    return dx_list, dy_list


def report(pairs: List[Tuple[Dict, Dict]], dx_list: List[float], dy_list: List[float]) -> None:
    print(f"\n=== 座標ずれ検証レポート ===")
    print(f"マッチしたペア数: {len(pairs)}")
    if not dx_list:
        print("マッチするペアがありませんでした。")
        return

    print(f"\n--- dx (OCR_x - GT_x) ---")
    print(f"  平均: {statistics.mean(dx_list):.3f} pt")
    print(f"  標準偏差: {statistics.stdev(dx_list):.3f} pt" if len(dx_list) > 1 else "  標準偏差: N/A")
    print(f"  最小: {min(dx_list):.3f} pt")
    print(f"  最大: {max(dx_list):.3f} pt")

    print(f"\n--- dy (OCR_y - GT_y) ---")
    print(f"  平均: {statistics.mean(dy_list):.3f} pt")
    print(f"  標準偏差: {statistics.stdev(dy_list):.3f} pt" if len(dy_list) > 1 else "  標準偏差: N/A")
    print(f"  最小: {min(dy_list):.3f} pt")
    print(f"  最大: {max(dy_list):.3f} pt")

    print(f"\n先頭10ペア:")
    for i, (gt, ocr) in enumerate(pairs[:10]):
        gt_x0, gt_y0, _, _ = gt["bbox"]
        print(
            f"  [{i+1}] GT='{gt['text'][:20]}' "
            f"gt_xy=({gt_x0:.1f},{gt_y0:.1f}) "
            f"ocr_xy=({ocr['x']:.1f},{ocr['y']:.1f}) "
            f"dx={dx_list[i]:.2f} dy={dy_list[i]:.2f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR座標ずれ検証スクリプト")
    parser.add_argument("text_pdf", help="テキスト込みPDF (ground truth)")
    parser.add_argument("image_pdf", help="画像のみPDF (OCR対象)")
    parser.add_argument("--dpi", type=int, default=300, help="OCR解像度 (default: 300)")
    args = parser.parse_args()

    text_pdf = Path(args.text_pdf)
    image_pdf = Path(args.image_pdf)

    print(f"Ground truth PDF: {text_pdf}")
    print(f"OCR対象PDF:       {image_pdf}")
    print(f"DPI:              {args.dpi}")

    print("\n[1/3] Ground truth 抽出中...")
    gt = extract_ground_truth(text_pdf)
    print(f"  スパン数: {len(gt)}")

    print("\n[2/3] OCR実行中...")
    ocr = run_ocr(image_pdf, dpi=args.dpi)
    print(f"  OCR結果数: {len(ocr)}")

    print("\n[3/3] マッチング中...")
    pairs = match_pairs(gt, ocr)
    dx_list, dy_list = compute_offsets(pairs)

    report(pairs, dx_list, dy_list)


if __name__ == "__main__":
    main()
