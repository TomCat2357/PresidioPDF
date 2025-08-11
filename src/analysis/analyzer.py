#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PresidioエンジンによるPII分析と重複除去
"""

import logging
import spacy
from presidio_analyzer import (
    AnalyzerEngine,
    PatternRecognizer,
    Pattern,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpEngineProvider
from typing import List, Dict

from core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class Analyzer:
    """Presidioエンジンの設定とPII分析を担当するクラス"""

    def __init__(self, config_manager: ConfigManager):
        """
        Args:
            config_manager: 設定管理インスタンス
        """
        self.config_manager = config_manager
        self.analyzer = self._setup_presidio()

    def _setup_presidio(self) -> AnalyzerEngine:
        """Presidioエンジンを初期化"""
        nlp = None
        try:
            # 設定からspaCyモデルを取得
            preferred_model = self.config_manager.get_spacy_model()
            fallback_models = self.config_manager.get_fallback_models()
            auto_download = self.config_manager.is_auto_download_enabled()

            model_name = None

            # 優先モデルを試行
            try:
                nlp = spacy.load(preferred_model)
                model_name = preferred_model
                logger.info(f"spaCyモデルを読み込みました: {model_name}")
            except OSError:
                raise OSError(
                    f"指定されたspaCyモデル '{preferred_model}' が見つかりません。モデルを正しくインストールしてください。"
                )

        except Exception as e:
            logger.error(f"spaCyモデルの読み込みでエラーが発生しました: {e}")
            raise

        self.nlp = nlp
        config_models = [{"lang_code": "ja", "model_name": model_name}]
        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": config_models,
            }
        )

        analyzer = AnalyzerEngine(
            nlp_engine=provider.create_engine(), supported_languages=["ja"]
        )

        # 既定の認識器のみを登録（追加ルールは独自パイプラインで適用）
        self._add_default_recognizers(analyzer)
        return analyzer

    # 旧方式（Presidioに直接登録）を保持する場合は上記で呼び出す
    # def _add_custom_recognizers(self, analyzer: AnalyzerEngine):
    #     ...

    # カスタム人名辞書のPresidio登録は廃止し、追加パターンとして独自適用する

    def _add_default_recognizers(self, analyzer: AnalyzerEngine):
        """デフォルトの認識器を追加"""
        # マイナンバー認識
        individual_number_recognizer = PatternRecognizer(
            supported_entity="INDIVIDUAL_NUMBER",
            supported_language="ja",
            patterns=[Pattern(name="マイナンバー", score=0.9, regex="[0-9]{11,13}")],
        )
        analyzer.registry.add_recognizer(individual_number_recognizer)

        # 年号認識
        year_recognizer = PatternRecognizer(
            supported_entity="YEAR",
            supported_language="ja",
            patterns=[
                Pattern(
                    name="年",
                    score=0.8,
                    regex="([1-9][0-9]{3}年|(令和|平成|昭和|大正|明治)([1-9][0-9]?)年)",
                )
            ],
        )
        analyzer.registry.add_recognizer(year_recognizer)

        # 敬称付き人名認識
        person_name_recognizer = PatternRecognizer(
            supported_entity="PERSON",
            supported_language="ja",
            patterns=[
                Pattern(
                    name="名前",
                    score=0.7,
                    regex=r"([\u4e00-\u9fff]+)(?:くん|さん|君|ちゃん|様)",
                )
            ],
        )
        analyzer.registry.add_recognizer(person_name_recognizer)

        # 電話番号認識
        phone_recognizer = PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            supported_language="ja",
            patterns=[
                Pattern(
                    name="電話番号", regex=r"0\d{1,4}[-]?\d{1,4}[-]?\d{4}", score=0.8
                )
            ],
        )
        analyzer.registry.add_recognizer(phone_recognizer)

    def analyze_text(self, text: str, entities: List[str] = None) -> List[Dict]:
        """テキストの個人情報を解析（大容量ファイル対応）"""
        if entities is None:
            entities = self.config_manager.get_enabled_entities()

        text_bytes = len(text.encode("utf-8"))
        if text_bytes > 45000:
            logger.info(
                f"大容量テキスト検出 ({text_bytes:,} bytes) - チャンク処理を実行"
            )
            return self._analyze_text_chunked(text, entities)

        return self._analyze_text_single(text, entities)

    def _analyze_text_single(self, text: str, entities: List[str]) -> List[Dict]:
        """単一テキストの個人情報解析（追加>モデル>除外）"""
        import re

        # 1) 追加パターンの適用（右→左適用、左定義が高優先、長さ無視）
        add_map = self.config_manager.get_additional_patterns_mapping()
        add_candidates = []
        priority_seq = []
        for etype, pats in add_map.items():
            if etype not in entities:
                continue
            # パターン順序: 左(0)が高優先。適用は右→左。
            for idx, pat in enumerate(pats):
                priority_seq.append((etype, idx, pat))
        # 探索: 右→左
        for etype, idx, pat in reversed(priority_seq):
            try:
                cre = re.compile(pat, re.MULTILINE)
            except re.error as e:
                logger.warning(f"無効な追加正規表現をスキップ: {pat}: {e}")
                continue
            for m in cre.finditer(text):
                s, e = m.span()
                if s == e:
                    continue
                add_candidates.append(
                    {
                        "start": s,
                        "end": e,
                        "entity_type": etype,
                        "text": text[s:e],
                        "_prio": idx,  # 低いほど高優先
                    }
                )

        # 追加候補の非重複化（優先度のみで解決）
        add_selected: List[Dict] = []
        occupied: List[tuple] = []
        for cand in sorted(add_candidates, key=lambda x: (x["_prio"], x["start"])):
            s, e = cand["start"], cand["end"]
            if any(not (e <= os or oe <= s) for (os, oe) in occupied):
                continue
            occupied.append((s, e))
            add_selected.append({k: v for k, v in cand.items() if not k.startswith("_")})

        # 2) モデル検出（既存Presidio + 固有名詞）
        analyzer_results = self.analyzer.analyze(text=text, language="ja", entities=entities)
        if "PROPER_NOUN" in entities:
            analyzer_results.extend(self._detect_proper_nouns(text))

        # 3) モデル結果に除外適用＆追加と重複するものを抑制
        def overlaps_any(span):
            s, e = span
            for os, oe in occupied:
                if not (e <= os or oe <= s):
                    return True
            return False

        model_filtered: List[Dict] = []
        for r in analyzer_results:
            if r.entity_type not in entities:
                continue
            s, e = r.start, r.end
            ent_text = text[s:e]
            refined_text = self._refine_entity_text(ent_text, r.entity_type, text, s, e)
            rs, re_ = self._calculate_refined_positions(text, s, e, refined_text)
            # 追加と重なればスキップ（追加優先）
            if overlaps_any((rs, re_)):
                continue
            # 除外はモデル結果のみに適用
            if self.config_manager.is_entity_excluded(r.entity_type, refined_text):
                logger.debug(f"エンティティ除外: '{refined_text}' ({r.entity_type})")
                continue
            model_filtered.append(
                {
                    "start": rs,
                    "end": re_,
                    "entity_type": r.entity_type,
                    "text": refined_text,
                }
            )

        results = add_selected + model_filtered
        if self.config_manager.is_deduplication_enabled():
            results = self._deduplicate_entities(results)
        return sorted(results, key=lambda x: x["start"])

    def _analyze_text_chunked(self, text: str, entities: List[str]) -> List[Dict]:
        """チャンク分割による大容量テキスト解析"""
        chunks = self._chunk_text(text)
        all_results = []

        logger.info(f"テキストを{len(chunks)}個のチャンクに分割して処理")

        for i, chunk_info in enumerate(chunks):
            chunk_text = chunk_info["text"]
            start_offset = chunk_info["start_offset"]

            try:
                logger.debug(
                    f"チャンク {i+1}/{len(chunks)} 処理中 (サイズ: {len(chunk_text.encode('utf-8'))} bytes)"
                )
                chunk_results = self._analyze_text_single(chunk_text, entities)

                for result in chunk_results:
                    result["start"] += len(text[:start_offset])
                    result["end"] += len(text[:start_offset])

                all_results.extend(chunk_results)

            except Exception as e:
                logger.error(f"チャンク {i+1} の処理でエラー: {e}")
                continue

        return sorted(all_results, key=lambda x: x["start"])

    def _detect_proper_nouns(self, text: str) -> List[RecognizerResult]:
        """固有名詞を検出（大容量テキスト対応）"""
        text_bytes = len(text.encode("utf-8"))
        if text_bytes > 45000:
            logger.debug(
                f"固有名詞検出: 大容量テキスト ({text_bytes:,} bytes) - チャンク処理"
            )
            return self._detect_proper_nouns_chunked(text)

        return self._detect_proper_nouns_single(text)

    def _detect_proper_nouns_single(self, text: str) -> List[RecognizerResult]:
        """単一テキストの固有名詞検出"""
        results = []
        doc = self.nlp(text)

        for token in doc:
            if token.pos_ == "PROPN":
                result = RecognizerResult(
                    entity_type="PROPER_NOUN",
                    start=token.idx,
                    end=token.idx + len(token.text),
                    score=0.85,
                    recognition_metadata={"recognizer_name": "ProperNounRecognizer"},
                )
                results.append(result)

        return results

    def _detect_proper_nouns_chunked(self, text: str) -> List[RecognizerResult]:
        """チャンク分割による大容量テキストの固有名詞検出"""
        chunks = self._chunk_text(text)
        all_results = []

        for i, chunk_info in enumerate(chunks):
            chunk_text = chunk_info["text"]
            start_offset = chunk_info["start_offset"]

            try:
                chunk_results = self._detect_proper_nouns_single(chunk_text)

                for result in chunk_results:
                    result.start += len(text[:start_offset])
                    result.end += len(text[:start_offset])

                all_results.extend(chunk_results)

            except Exception as e:
                logger.error(f"固有名詞検出 チャンク {i+1} でエラー: {e}")
                continue

        return all_results

    def _chunk_text(self, text: str, max_bytes: int = 45000) -> List[Dict]:
        """テキストをチャンクに分割（spaCyの制限対応）"""
        chunks = []
        text_bytes = text.encode("utf-8")

        if len(text_bytes) <= max_bytes:
            return [{"text": text, "start_offset": 0}]

        sentences = text.split("\n")
        current_chunk = ""
        current_offset = 0

        for sentence in sentences:
            sentence_with_newline = sentence + "\n"
            test_chunk = current_chunk + sentence_with_newline

            if len(test_chunk.encode("utf-8")) > max_bytes and current_chunk:
                chunks.append(
                    {"text": current_chunk.rstrip(), "start_offset": current_offset}
                )
                current_offset += len(current_chunk.encode("utf-8"))
                current_chunk = sentence_with_newline
            else:
                current_chunk = test_chunk

        if current_chunk.strip():
            chunks.append(
                {"text": current_chunk.rstrip(), "start_offset": current_offset}
            )

        return chunks

    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """重複するエンティティを除去"""
        if not entities:
            return entities

        priority = self.config_manager.get_deduplication_priority()

        sorted_entities = sorted(entities, key=lambda x: x["start"])
        deduplicated = []

        for current_entity in sorted_entities:
            should_add = True
            entities_to_remove = []

            for i, existing_entity in enumerate(deduplicated):
                if self._has_overlap(current_entity, existing_entity):
                    current_should_win = self._should_current_entity_win(
                        current_entity, existing_entity, priority
                    )

                    if current_should_win:
                        entities_to_remove.append(i)
                    else:
                        should_add = False
                        break

            for i in sorted(entities_to_remove, reverse=True):
                removed_entity = deduplicated.pop(i)
                logger.debug(
                    f"重複除去: '{removed_entity['text']}' ({removed_entity['entity_type']}) を除去"
                )

            if should_add:
                deduplicated.append(current_entity)
            else:
                logger.debug(
                    f"重複除去: '{current_entity['text']}' ({current_entity['entity_type']}) を除去"
                )

        original_count = len(entities)
        deduplicated_count = len(deduplicated)
        if original_count != deduplicated_count:
            logger.info(
                f"重複除去: {original_count}件 → {deduplicated_count}件 ({original_count - deduplicated_count}件を除去)"
            )

        return deduplicated

    def _has_overlap(self, entity1: Dict, entity2: Dict) -> bool:
        """2つのエンティティが重複しているかを判定"""
        method = self.config_manager.get_deduplication_method()

        start1, end1 = entity1["start"], entity1["end"]
        start2, end2 = entity2["start"], entity2["end"]

        if method == "exact":
            return start1 == start2 and end1 == end2
        elif method == "contain":
            return (start1 <= start2 and end1 >= end2) or (
                start2 <= start1 and end2 >= end1
            )
        elif method == "overlap":
            overlap_mode = self.config_manager.get_deduplication_overlap_mode()

            if overlap_mode == "contain_only":
                return (start1 <= start2 and end1 >= end2) or (
                    start2 <= start1 and end2 >= end1
                )
            elif overlap_mode == "partial_overlap":
                return not (end1 <= start2 or end2 <= start1)
            else:
                logger.warning(
                    f"不明な重複モード: {overlap_mode}. デフォルトのpartial_overlapを使用します。"
                )
                return not (end1 <= start2 or end2 <= start1)
        else:
            logger.warning(
                f"不明な重複判定方法: {method}. デフォルトのoverlapを使用します。"
            )
            return not (end1 <= start2 or end2 <= start1)

    def _should_current_entity_win(
        self, current_entity: Dict, existing_entity: Dict, priority: str
    ) -> bool:
        """2つのエンティティを比較して、現在のエンティティが優先されるべきかを判定"""
        if priority == "wider_range":
            current_range = current_entity["end"] - current_entity["start"]
            existing_range = existing_entity["end"] - existing_entity["start"]
            if current_range != existing_range:
                return current_range > existing_range
            return current_entity["start"] < existing_entity["start"]

        elif priority == "narrower_range":
            current_range = current_entity["end"] - current_entity["start"]
            existing_range = existing_entity["end"] - existing_entity["start"]
            if current_range != existing_range:
                return current_range < existing_range
            return current_entity["start"] < existing_entity["start"]

        elif priority == "entity_type":
            entity_order = self.config_manager.get_entity_priority_order()
            try:
                current_priority = entity_order.index(current_entity["entity_type"])
            except ValueError:
                current_priority = len(entity_order)

            try:
                existing_priority = entity_order.index(existing_entity["entity_type"])
            except ValueError:
                existing_priority = len(entity_order)

            if current_priority != existing_priority:
                return current_priority < existing_priority
            return current_entity["start"] < existing_entity["start"]

        else:
            current_range = current_entity["end"] - current_entity["start"]
            existing_range = existing_entity["end"] - existing_entity["start"]
            if current_range != existing_range:
                return current_range > existing_range
            return current_entity["start"] < existing_entity["start"]

    def _refine_entity_text(
        self, entity_text: str, entity_type: str, full_text: str, start: int, end: int
    ) -> str:
        """エンティティタイプに応じてテキスト境界を調整"""
        import re

        if entity_type == "PERSON":
            refined = re.sub(r"[0-9\-\s]*", "", entity_text).strip()
            if refined:
                return refined

        elif entity_type == "LOCATION":
            refined = re.sub(r"[0-9\-\s]*", "", entity_text).strip()
            if refined:
                return refined

        elif entity_type == "PHONE_NUMBER":
            refined = re.findall(r"[0-9\-]+", entity_text)
            if refined:
                return "".join(refined)

        return entity_text

    def _calculate_refined_positions(
        self, full_text: str, original_start: int, original_end: int, refined_text: str
    ) -> tuple:
        """調整されたテキストの新しい位置を計算"""
        original_text = full_text[original_start:original_end]

        if refined_text in original_text:
            relative_start = original_text.find(refined_text)
            if relative_start != -1:
                new_start = original_start + relative_start
                new_end = new_start + len(refined_text)
                return new_start, new_end

        return original_start, original_end
