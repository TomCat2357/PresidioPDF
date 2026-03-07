#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""PDFテキスト抽出時の可視性判定ヘルパー。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set, Tuple


def get_span_text(span: Dict[str, Any]) -> str:
    """span から文字列を抽出する。"""
    chars = span.get("chars")
    if isinstance(chars, list) and chars:
        return "".join(str(char.get("c", "")) for char in chars)
    return str(span.get("text", "") or "")


def _point_to_key(point: Iterable[Any], digits: int = 3) -> Optional[Tuple[float, float]]:
    """座標点を比較用キーへ正規化する。"""
    try:
        values = list(point)
    except TypeError:
        return None

    try:
        if len(values) < 2:
            return None
        return tuple(round(float(value), digits) for value in values[:2])
    except (TypeError, ValueError):
        return None


def _trace_char_to_key(char_info: Tuple[Any, ...], digits: int = 3) -> Optional[Tuple[float, float, str]]:
    """texttrace 文字タプルを比較用キーへ変換する。"""
    if not isinstance(char_info, tuple) or len(char_info) < 3:
        return None

    point_key = _point_to_key(char_info[2], digits=digits)
    if point_key is None:
        return None

    try:
        char_value = chr(int(char_info[0]))
    except (TypeError, ValueError, OverflowError):
        return None

    return (point_key[0], point_key[1], char_value)


def _raw_char_to_key(char_info: Dict[str, Any], digits: int = 3) -> Optional[Tuple[float, float, str]]:
    """rawdict 文字辞書を比較用キーへ変換する。"""
    point_key = _point_to_key(char_info.get("origin"), digits=digits)
    if point_key is None:
        return None

    char_value = str(char_info.get("c", "") or "")
    if not char_value:
        return None

    return (point_key[0], point_key[1], char_value)


def build_invisible_char_keys(page: Any) -> Set[Tuple[float, float, str]]:
    """opacity=0 の不可視文字キー集合を返す。"""
    invisible_keys: Set[Tuple[float, float, str]] = set()

    try:
        traces = page.get_texttrace()
    except Exception:
        return invisible_keys

    for trace in traces or []:
        try:
            opacity = float(trace.get("opacity", 1.0))
        except (TypeError, ValueError):
            opacity = 1.0
        if opacity > 0.0:
            continue

        for char_info in trace.get("chars", ()) or ():
            key = _trace_char_to_key(char_info)
            if key is not None:
                invisible_keys.add(key)

    return invisible_keys


def is_invisible_char(char_info: Dict[str, Any], invisible_char_keys: Set[Tuple[float, float, str]]) -> bool:
    """rawdict 文字が不可視文字集合に含まれるかを返す。"""
    if not invisible_char_keys:
        return False

    key = _raw_char_to_key(char_info)
    if key is None:
        return False
    return key in invisible_char_keys
