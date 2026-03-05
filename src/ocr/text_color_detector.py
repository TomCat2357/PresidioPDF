"""OCRテキスト色自動検出モジュール。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from PIL import Image as PILImage


def detect_text_color(
    image: "PILImage.Image",
    bbox: Tuple[float, float, float, float],
) -> Tuple[int, int, int]:
    """
    画像のbbox領域からテキスト色を自動検出する。

    Args:
        image: PIL.Image オブジェクト（RGB想定）
        bbox: (x, y, w, h) - ピクセル座標

    Returns:
        (R, G, B) タプル (0-255)。前景ピクセルが少なすぎる場合は (0, 0, 0)。
    """
    x, y, w, h = bbox
    x0, y0 = int(x), int(y)
    x1, y1 = int(x + w), int(y + h)

    img_w, img_h = image.size
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(img_w, x1)
    y1 = min(img_h, y1)

    if x1 <= x0 or y1 <= y0:
        return (0, 0, 0)

    cropped = image.crop((x0, y0, x1, y1))
    if cropped.mode != "RGB":
        cropped = cropped.convert("RGB")

    cw, ch = cropped.size
    pixels = list(cropped.getdata())  # [(R, G, B), ...]

    # 外周ピクセルから背景色を推定（中央値）
    border_pixels = []
    for px in range(cw):
        border_pixels.append(pixels[px])
        border_pixels.append(pixels[(ch - 1) * cw + px])
    for py in range(1, ch - 1):
        border_pixels.append(pixels[py * cw])
        border_pixels.append(pixels[py * cw + cw - 1])

    if not border_pixels:
        border_pixels = pixels

    def _median_channel(lst: list, ch_idx: int) -> int:
        vals = sorted(p[ch_idx] for p in lst)
        return vals[len(vals) // 2]

    bg_r = _median_channel(border_pixels, 0)
    bg_g = _median_channel(border_pixels, 1)
    bg_b = _median_channel(border_pixels, 2)

    # 背景色とのユークリッド色差が閾値超のピクセルを前景(テキスト)として抽出
    threshold_sq = 50 * 50
    foreground_pixels = []
    for p in pixels:
        dr = p[0] - bg_r
        dg = p[1] - bg_g
        db = p[2] - bg_b
        if dr * dr + dg * dg + db * db > threshold_sq:
            foreground_pixels.append(p)

    # 前景ピクセルが少なすぎる場合はフォールバック
    min_foreground = max(1, len(pixels) // 20)
    if len(foreground_pixels) < min_foreground:
        return (0, 0, 0)

    # 前景ピクセルの各チャンネル中央値をテキスト色として返却
    text_r = _median_channel(foreground_pixels, 0)
    text_g = _median_channel(foreground_pixels, 1)
    text_b = _median_channel(foreground_pixels, 2)

    return (text_r, text_g, text_b)
