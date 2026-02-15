#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
注釈関連の共通ユーティリティ

PDFMasker と PDFAnnotator で共有される注釈コンテンツのパース処理を集約。
"""

import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def parse_annotation_content(content: str) -> Dict:
    """注釈/ハイライトのcontent文字列をパースして構造化データを取得

    detect_word:"value",entity_type:"TYPE" 形式のパース。

    Args:
        content: 注釈のcontent文字列

    Returns:
        Dict: パース結果 (detect_word, entity_type など)
    """
    result = {}
    try:
        detect_word_match = re.search(r'detect_word:"([^"]*)"', content)
        if detect_word_match:
            result["detect_word"] = detect_word_match.group(1)

        entity_type_match = re.search(r'entity_type:"([^"]*)"', content)
        if entity_type_match:
            result["entity_type"] = entity_type_match.group(1)

    except Exception as e:
        logger.debug(f"注釈コンテンツパースエラー: {e}")

    return result
