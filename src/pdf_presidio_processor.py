#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyMuPDF版 PDF個人情報検出・マスキングプロセッサー
高性能なPyMuPDFライブラリを使用してPDF処理を実行します。
"""

import os
import sys
import logging
import json
import shutil
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Union
import click
import spacy
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color, red, green, blue, black, yellow, purple, orange
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

from config_manager import ConfigManager

logger = logging.getLogger(__name__)

class PDFPresidioProcessor:
    """PyMuPDF版 PDF個人情報検出・マスキングプロセッサー"""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Args:
            config_manager: 設定管理インスタンス
        """
        self.config_manager = config_manager or ConfigManager()
        self.nlp = None
        self.analyzer = None
        self.processing_stats = {
            'files_processed': 0,
            'files_failed': 0,
            'total_entities_found': 0,
            'entities_by_type': {},
            'start_time': datetime.now()
        }
        self._setup_logging()
        self._setup_presidio()
    
    def _setup_logging(self):
        """ログ設定を初期化"""
        log_config = self.config_manager.get_logging_config()
        level = getattr(logging, log_config['level'].upper(), logging.INFO)
        logging.getLogger().setLevel(level)
        
        if log_config.get('log_to_file', False):
            file_handler = logging.FileHandler(
                log_config['log_file_path'], 
                encoding='utf-8'
            )
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            logging.getLogger().addHandler(file_handler)
            logger.info(f"ログファイルに出力: {log_config['log_file_path']}")
    
    def _setup_presidio(self):
        """Presidioエンジンを初期化"""
        try:
            # 設定からspaCyモデルを取得
            preferred_model = self.config_manager.get_spacy_model()
            fallback_models = self.config_manager.get_fallback_models()
            auto_download = self.config_manager.is_auto_download_enabled()
            
            model_name = None
            
            # 優先モデルを試行
            try:
                self.nlp = spacy.load(preferred_model)
                model_name = preferred_model
                logger.info(f"spaCyモデルを読み込みました: {model_name}")
            except OSError:
                logger.warning(f"優先モデル '{preferred_model}' が見つかりません。フォールバックモデルを試行します。")
                
                # フォールバックモデルを順番に試行
                for fallback_model in fallback_models:
                    if fallback_model == preferred_model:
                        continue  # 既に試行済み
                    try:
                        self.nlp = spacy.load(fallback_model)
                        model_name = fallback_model
                        logger.info(f"フォールバックモデルを読み込みました: {model_name}")
                        break
                    except OSError:
                        logger.debug(f"フォールバックモデル '{fallback_model}' が見つかりません。")
                        continue
                
                # すべてのモデルが見つからない場合
                if model_name is None:
                    if auto_download:
                        logger.info("利用可能なモデルが見つかりません。ja_core_news_smを自動ダウンロードを試行します。")
                        try:
                            import subprocess
                            import sys
                            subprocess.check_call([sys.executable, "-m", "pip", "install", 
                                                 "https://github.com/explosion/spacy-models/releases/download/ja_core_news_sm-3.7.0/ja_core_news_sm-3.7.0-py3-none-any.whl"])
                            self.nlp = spacy.load("ja_core_news_sm")
                            model_name = "ja_core_news_sm"
                            logger.info("ja_core_news_smを自動ダウンロードして読み込みました。")
                        except Exception as e:
                            logger.error(f"モデルの自動ダウンロードに失敗しました: {e}")
                            raise OSError("日本語spaCyモデルが見つかりません。'uv pip install https://github.com/explosion/spacy-models/releases/download/ja_core_news_sm-3.7.0/ja_core_news_sm-3.7.0-py3-none-any.whl'を実行してください。")
                    else:
                        raise OSError("日本語spaCyモデルが見つかりません。'uv pip install https://github.com/explosion/spacy-models/releases/download/ja_core_news_sm-3.7.0/ja_core_news_sm-3.7.0-py3-none-any.whl'を実行してください。")
        
        except Exception as e:
            logger.error(f"spaCyモデルの読み込みでエラーが発生しました: {e}")
            raise
        
        config_models = [{"lang_code": "ja", "model_name": model_name}]
        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": config_models,
            }
        )
        
        self.analyzer = AnalyzerEngine(
            nlp_engine=provider.create_engine(),
            supported_languages=["ja"]
        )
        
        self._add_custom_recognizers()
    
    def _add_custom_recognizers(self):
        """カスタム認識器を追加"""
        # デフォルトの認識器を追加
        self._add_default_recognizers()
        
        # カスタム人名辞書の認識器を追加
        self._add_custom_name_recognizers()
        
        # 設定ファイルからカスタム認識器を追加
        custom_recognizers = self.config_manager.get_custom_recognizers()
        for recognizer_name, config in custom_recognizers.items():
            try:
                patterns = []
                for pattern_config in config.get('patterns', []):
                    pattern = Pattern(
                        name=pattern_config['name'],
                        regex=pattern_config['regex'],
                        score=pattern_config['score']
                    )
                    patterns.append(pattern)
                
                recognizer = PatternRecognizer(
                    supported_entity=config['entity_type'],
                    supported_language="ja",
                    patterns=patterns
                )
                
                self.analyzer.registry.add_recognizer(recognizer)
                logger.info(f"カスタム認識器を追加: {recognizer_name}")
            except Exception as e:
                logger.error(f"カスタム認識器の追加でエラー ({recognizer_name}): {e}")
    
    def _add_custom_name_recognizers(self):
        """カスタム人名辞書の認識器を追加"""
        if not self.config_manager.is_custom_names_enabled():
            return
        
        patterns = []
        
        # 辞書リスト方式の処理
        name_list = self.config_manager.get_custom_name_list()
        if name_list:
            # リストの各名前に対して正規表現パターンを作成
            name_regex = "|".join(f"({name})" for name in name_list)
            pattern = Pattern(
                name="カスタム人名リスト",
                regex=name_regex,
                score=0.9
            )
            patterns.append(pattern)
            logger.info(f"カスタム人名リストを追加: {len(name_list)}個の名前")
        
        # パターン方式の処理
        name_patterns = self.config_manager.get_custom_name_patterns()
        for pattern_config in name_patterns:
            try:
                pattern = Pattern(
                    name=pattern_config['name'],
                    regex=pattern_config['regex'],
                    score=pattern_config['score']
                )
                patterns.append(pattern)
                logger.info(f"カスタム人名パターンを追加: {pattern_config['name']}")
            except Exception as e:
                logger.error(f"カスタム人名パターンの追加でエラー ({pattern_config.get('name', 'Unknown')}): {e}")
        
        # パターンがある場合、認識器を追加
        if patterns:
            custom_name_recognizer = PatternRecognizer(
                supported_entity="PERSON",
                supported_language="ja",
                patterns=patterns
            )
            
            self.analyzer.registry.add_recognizer(custom_name_recognizer)
            logger.info(f"カスタム人名認識器を追加: {len(patterns)}個のパターン")
    
    def _add_default_recognizers(self):
        """デフォルトの認識器を追加"""
        # マイナンバー認識
        threshold = self.config_manager.get_threshold('INDIVIDUAL_NUMBER')
        individual_number_recognizer = PatternRecognizer(
            supported_entity="INDIVIDUAL_NUMBER",
            supported_language="ja",
            patterns=[Pattern(name="マイナンバー", score=threshold, regex="[0-9]{11,13}")],
        )
        self.analyzer.registry.add_recognizer(individual_number_recognizer)
        
        # 年号認識
        threshold = self.config_manager.get_threshold('YEAR')
        year_recognizer = PatternRecognizer(
            supported_entity="YEAR",
            supported_language="ja",
            patterns=[
                Pattern(
                    name="年",
                    score=threshold,
                    regex="([1-9][0-9]{3}年|(令和|平成|昭和|大正|明治)([1-9][0-9]?)年)",
                )
            ],
        )
        self.analyzer.registry.add_recognizer(year_recognizer)
        
        # 敬称付き人名認識
        threshold = self.config_manager.get_threshold('PERSON')
        person_name_recognizer = PatternRecognizer(
            supported_entity="PERSON",
            supported_language="ja",
            patterns=[
                Pattern(
                    name="名前",
                    score=threshold,
                    regex=r'([\u4e00-\u9fff]+)(?:くん|さん|君|ちゃん|様)',
                )
            ],
        )
        self.analyzer.registry.add_recognizer(person_name_recognizer)
        
        # 電話番号認識
        threshold = self.config_manager.get_threshold('PHONE_NUMBER')
        phone_recognizer = PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            supported_language="ja",
            patterns=[Pattern(name="電話番号", regex=r'0\d{1,4}[-]?\d{1,4}[-]?\d{4}', score=threshold)]
        )
        self.analyzer.registry.add_recognizer(phone_recognizer)
    
    def _detect_proper_nouns(self, text: str, score: float = None) -> List[RecognizerResult]:
        """固有名詞を検出（大容量テキスト対応）"""
        if score is None:
            score = self.config_manager.get_threshold('PROPER_NOUN')
        
        # テキストサイズチェック
        text_bytes = len(text.encode('utf-8'))
        if text_bytes > 45000:
            logger.debug(f"固有名詞検出: 大容量テキスト ({text_bytes:,} bytes) - チャンク処理")
            return self._detect_proper_nouns_chunked(text, score)
        
        return self._detect_proper_nouns_single(text, score)

    def _detect_proper_nouns_single(self, text: str, score: float) -> List[RecognizerResult]:
        """単一テキストの固有名詞検出"""
        results = []
        doc = self.nlp(text)
        
        for token in doc:
            if token.pos_ == "PROPN":
                result = RecognizerResult(
                    entity_type="PROPER_NOUN",
                    start=token.idx,
                    end=token.idx + len(token.text),
                    score=score,
                    recognition_metadata={'recognizer_name': 'ProperNounRecognizer'}
                )
                results.append(result)
        
        return results

    def _detect_proper_nouns_chunked(self, text: str, score: float) -> List[RecognizerResult]:
        """チャンク分割による大容量テキストの固有名詞検出"""
        chunks = self._chunk_text(text)
        all_results = []
        
        for i, chunk_info in enumerate(chunks):
            chunk_text = chunk_info['text']
            start_offset = chunk_info['start_offset']
            
            try:
                chunk_results = self._detect_proper_nouns_single(chunk_text, score)
                
                # チャンクの結果の位置を全体テキストでの位置に調整
                for result in chunk_results:
                    result.start += len(text[:start_offset])
                    result.end += len(text[:start_offset])
                
                all_results.extend(chunk_results)
                
            except Exception as e:
                logger.error(f"固有名詞検出 チャンク {i+1} でエラー: {e}")
                continue
        
        return all_results
    
    def extract_pdf_text(self, pdf_path: str) -> Dict[str, Any]:
        """PyMuPDFを使用してPDFからテキストと位置情報を抽出"""
        try:
            doc = fitz.open(pdf_path)
            pages_data = []
            full_text = ""
            current_offset = 0
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                
                # 文字レベルの詳細情報を取得
                text_dict = page.get_text("dict")
                
                # 各文字の位置情報を計算
                chars = []
                for block in text_dict.get("blocks", []):
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line["spans"]:
                                text = span.get("text", "")
                                bbox = span.get("bbox", [0, 0, 0, 0])
                                for i, char in enumerate(text):
                                    char_info = {
                                        'text': char,
                                        'x0': bbox[0] + i * (bbox[2] - bbox[0]) / len(text) if text else bbox[0],
                                        'y0': bbox[1],
                                        'x1': bbox[0] + (i+1) * (bbox[2] - bbox[0]) / len(text) if text else bbox[2],
                                        'y1': bbox[3],
                                        'fontname': span.get('font', ''),
                                        'size': span.get('size', 12)
                                    }
                                    chars.append(char_info)
                
                page_data = {
                    'page_number': page_num + 1,
                    'text': page_text,
                    'chars': chars,
                    'bbox': page.rect,
                    'text_start_offset': current_offset,
                    'text_end_offset': current_offset + len(page_text),
                    'page_object': page  # PyMuPDFのページオブジェクトを保持
                }
                
                pages_data.append(page_data)
                full_text += page_text + "\n"
                current_offset += len(page_text) + 1  # +1 for newline
            
            return {
                'full_text': full_text,
                'pages': pages_data,
                'total_pages': len(doc),
                'document': doc  # ドキュメントオブジェクトを保持
            }
        
        except Exception as e:
            logger.error(f"PDFテキスト抽出エラー: {e}")
            raise
    
    def analyze_pdf(self, pdf_path: str) -> List[Dict]:
        """PDFの個人情報を解析"""
        logger.info(f"PDF解析開始: {pdf_path}")
        
        # PDFからテキストを抽出
        pdf_data = self.extract_pdf_text(pdf_path)
        full_text = pdf_data['full_text']
        
        # 個人情報を検出
        enabled_entities = self.config_manager.get_enabled_entities()
        results = self.analyze_text(full_text, enabled_entities)
        
        # 結果にページ情報を追加
        for result in results:
            result['pdf_data'] = pdf_data
            result['page_info'] = self._find_page_for_position(result['start'], pdf_data['pages'])
            # テキスト位置から座標位置を計算
            result['coordinates'] = self._calculate_text_coordinates(
                result['start'], result['end'], pdf_data['pages']
            )
        
        logger.info(f"PDF解析完了: {len(results)}件の個人情報を検出")
        return results
    
    def _find_page_for_position(self, text_position: int, pages: List[Dict]) -> Dict:
        """テキスト位置に対応するページ情報を取得"""
        for page_data in pages:
            if page_data['text_start_offset'] <= text_position <= page_data['text_end_offset']:
                return {
                    'page_number': page_data['page_number'],
                    'relative_position': text_position - page_data['text_start_offset']
                }
        return {'page_number': 1, 'relative_position': text_position}
    
    def _calculate_text_coordinates(self, start_pos: int, end_pos: int, pages: List[Dict]) -> Dict:
        """テキスト位置から座標を計算"""
        for page_data in pages:
            if page_data['text_start_offset'] <= start_pos <= page_data['text_end_offset']:
                relative_start = start_pos - page_data['text_start_offset']
                relative_end = min(end_pos - page_data['text_start_offset'], len(page_data['text']))
                
                # PyMuPDFを使用してより正確な座標を取得
                page_obj = page_data.get('page_object')
                if page_obj:
                    try:
                        # テキストインスタンスを検索
                        text_instances = page_obj.search_for(page_data['text'][relative_start:relative_end])
                        if text_instances:
                            # 最初のマッチした位置を使用
                            rect = text_instances[0]
                            return {
                                'page_number': page_data['page_number'],
                                'x0': float(rect.x0),
                                'y0': float(rect.y0),
                                'x1': float(rect.x1),
                                'y1': float(rect.y1)
                            }
                    except Exception as e:
                        logger.debug(f"テキスト検索でエラー: {e}")
                
                # フォールバック: 推定座標（より安全な値を使用）
                page_height = float(page_data['bbox'].height) if hasattr(page_data['bbox'], 'height') else 792.0
                line_height = 20.0
                margin_left = 50.0
                margin_top = 50.0
                
                # テキスト位置に基づく推定行数
                estimated_line = relative_start // 50  # 1行あたり約50文字と仮定
                
                y_pos = page_height - margin_top - (estimated_line * line_height)
                
                # 座標が有効な範囲内にあることを確認
                x0 = max(margin_left, 50.0)
                y0 = max(10.0, min(y_pos, page_height - 10.0))
                x1 = min(x0 + 150.0, page_data['bbox'].width - 10.0 if hasattr(page_data['bbox'], 'width') else 600.0)
                y1 = min(y0 + line_height, page_height - 10.0)
                
                return {
                    'page_number': page_data['page_number'],
                    'x0': x0,
                    'y0': y0,
                    'x1': x1,
                    'y1': y1
                }
        
        # 最終フォールバック
        return {
            'page_number': 1, 
            'x0': 50.0, 
            'y0': 700.0, 
            'x1': 200.0, 
            'y1': 720.0
        }
    
    def _chunk_text(self, text: str, max_bytes: int = 45000) -> List[Dict]:
        """テキストをチャンクに分割（spaCyの制限対応）"""
        chunks = []
        text_bytes = text.encode('utf-8')
        
        if len(text_bytes) <= max_bytes:
            return [{'text': text, 'start_offset': 0}]
        
        # 文や段落の境界で分割
        sentences = text.split('\n')
        current_chunk = ""
        current_offset = 0
        
        for sentence in sentences:
            sentence_with_newline = sentence + '\n'
            test_chunk = current_chunk + sentence_with_newline
            
            if len(test_chunk.encode('utf-8')) > max_bytes and current_chunk:
                # 現在のチャンクを保存
                chunks.append({
                    'text': current_chunk.rstrip(),
                    'start_offset': current_offset
                })
                current_offset += len(current_chunk.encode('utf-8'))
                current_chunk = sentence_with_newline
            else:
                current_chunk = test_chunk
        
        # 最後のチャンクを追加
        if current_chunk.strip():
            chunks.append({
                'text': current_chunk.rstrip(),
                'start_offset': current_offset
            })
        
        return chunks

    def analyze_text(self, text: str, entities: List[str] = None) -> List[Dict]:
        """テキストの個人情報を解析（大容量ファイル対応）"""
        if entities is None:
            entities = self.config_manager.get_enabled_entities()
        
        # テキストサイズチェック
        text_bytes = len(text.encode('utf-8'))
        if text_bytes > 45000:
            logger.info(f"大容量テキスト検出 ({text_bytes:,} bytes) - チャンク処理を実行")
            return self._analyze_text_chunked(text, entities)
        
        return self._analyze_text_single(text, entities)

    def _analyze_text_single(self, text: str, entities: List[str]) -> List[Dict]:
        """単一テキストの個人情報解析"""
        analyzer_results = self.analyzer.analyze(text=text, language="ja", entities=entities)
        
        if "PROPER_NOUN" in entities:
            proper_noun_results = self._detect_proper_nouns(text)
            analyzer_results.extend(proper_noun_results)
        
        results = []
        for result in analyzer_results:
            if result.entity_type in entities:
                # 閾値チェック
                min_score = self.config_manager.get_threshold(result.entity_type)
                if result.score >= min_score:
                    # エンティティ除外チェック
                    entity_text = text[result.start:result.end]
                    if not self.config_manager.is_entity_excluded(result.entity_type, entity_text):
                        results.append({
                            'start': result.start,
                            'end': result.end,
                            'score': result.score,
                            'entity_type': result.entity_type,
                            'text': entity_text
                        })
                    else:
                        logger.debug(f"エンティティ除外: '{entity_text}' ({result.entity_type})")
        
        # 重複除去処理（オプション）
        if self.config_manager.is_deduplication_enabled():
            results = self._deduplicate_entities(results)
        
        return sorted(results, key=lambda x: x['start'])
    
    def _has_overlap(self, entity1: Dict, entity2: Dict) -> bool:
        """2つのエンティティが重複しているかを判定"""
        method = self.config_manager.get_deduplication_method()
        
        start1, end1 = entity1['start'], entity1['end']
        start2, end2 = entity2['start'], entity2['end']
        
        if method == "exact":
            # 完全一致
            return start1 == start2 and end1 == end2
        elif method == "contain":
            # 包含関係（一方が他方を包含）
            return (start1 <= start2 and end1 >= end2) or (start2 <= start1 and end2 >= end1)
        elif method == "overlap":
            # 重複判定 - overlap_modeによって判定方法を変更
            overlap_mode = self.config_manager.get_deduplication_overlap_mode()
            
            if overlap_mode == "contain_only":
                # 包含関係のみ（一方が他方を完全に包含する場合のみ重複とみなす）
                return (start1 <= start2 and end1 >= end2) or (start2 <= start1 and end2 >= end1)
            elif overlap_mode == "partial_overlap":
                # 部分重複も含む（少しでも重なれば重複とみなす）
                return not (end1 <= start2 or end2 <= start1)
            else:
                logger.warning(f"不明な重複モード: {overlap_mode}. デフォルトのpartial_overlapを使用します。")
                return not (end1 <= start2 or end2 <= start1)
        else:
            logger.warning(f"不明な重複判定方法: {method}. デフォルトのoverlapを使用します。")
            # デフォルトはpartial_overlap
            return not (end1 <= start2 or end2 <= start1)
    
    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """重複するエンティティを除去"""
        if not entities:
            return entities
        
        priority = self.config_manager.get_deduplication_priority()
        
        # スタート位置でソート
        sorted_entities = sorted(entities, key=lambda x: x['start'])
        deduplicated = []
        
        for current_entity in sorted_entities:
            should_add = True
            entities_to_remove = []
            
            # 既に追加されたエンティティと重複チェック
            for i, existing_entity in enumerate(deduplicated):
                if self._has_overlap(current_entity, existing_entity):
                    # 重複が見つかった場合、優先順位に基づいて判定
                    current_should_win = self._should_current_entity_win(current_entity, existing_entity, priority)
                    
                    if current_should_win:
                        # 現在のエンティティの方が優先度が高い場合、既存を削除対象に
                        entities_to_remove.append(i)
                    else:
                        # 既存のエンティティの方が優先度が高い場合、現在を追加しない
                        should_add = False
                        break
            
            # 削除対象のエンティティを削除（逆順で削除してインデックスのずれを防ぐ）
            for i in sorted(entities_to_remove, reverse=True):
                removed_entity = deduplicated.pop(i)
                logger.debug(f"重複除去: '{removed_entity['text']}' ({removed_entity['entity_type']}, score={removed_entity['score']:.3f}) を除去")
            
            # 現在のエンティティを追加
            if should_add:
                deduplicated.append(current_entity)
            else:
                logger.debug(f"重複除去: '{current_entity['text']}' ({current_entity['entity_type']}, score={current_entity['score']:.3f}) を除去")
        
        original_count = len(entities)
        deduplicated_count = len(deduplicated)
        if original_count != deduplicated_count:
            logger.info(f"重複除去: {original_count}件 → {deduplicated_count}件 ({original_count - deduplicated_count}件を除去)")
        
        return deduplicated
    
    def _should_current_entity_win(self, current_entity: Dict, existing_entity: Dict, priority: str) -> bool:
        """2つのエンティティを比較して、現在のエンティティが優先されるべきかを判定"""
        if priority == "score":
            # スコア優先
            return current_entity['score'] > existing_entity['score']
        
        elif priority == "wider_range":
            # 広い範囲優先
            current_range = current_entity['end'] - current_entity['start']
            existing_range = existing_entity['end'] - existing_entity['start']
            if current_range != existing_range:
                return current_range > existing_range
            # 範囲が同じ場合はスコアで判定
            return current_entity['score'] > existing_entity['score']
        
        elif priority == "narrower_range":
            # 狭い範囲優先
            current_range = current_entity['end'] - current_entity['start']
            existing_range = existing_entity['end'] - existing_entity['start']
            if current_range != existing_range:
                return current_range < existing_range
            # 範囲が同じ場合はスコアで判定
            return current_entity['score'] > existing_entity['score']
        
        elif priority == "entity_type":
            # エンティティタイプ優先
            entity_order = self.config_manager.get_entity_priority_order()
            try:
                current_priority = entity_order.index(current_entity['entity_type'])
            except ValueError:
                current_priority = len(entity_order)  # 未知のタイプは最低優先度
            
            try:
                existing_priority = entity_order.index(existing_entity['entity_type'])
            except ValueError:
                existing_priority = len(entity_order)  # 未知のタイプは最低優先度
            
            if current_priority != existing_priority:
                return current_priority < existing_priority  # インデックスが小さい方が高優先度
            # エンティティタイプが同じ場合はスコアで判定
            return current_entity['score'] > existing_entity['score']
        
        else:
            # 未知の優先順位基準、デフォルトでスコア判定
            logger.warning(f"未サポートの優先順位基準: {priority}. スコア基準を使用します。")
            return current_entity['score'] > existing_entity['score']

    def _analyze_text_chunked(self, text: str, entities: List[str]) -> List[Dict]:
        """チャンク分割による大容量テキスト解析"""
        chunks = self._chunk_text(text)
        all_results = []
        
        logger.info(f"テキストを{len(chunks)}個のチャンクに分割して処理")
        
        for i, chunk_info in enumerate(chunks):
            chunk_text = chunk_info['text']
            start_offset = chunk_info['start_offset']
            
            try:
                logger.debug(f"チャンク {i+1}/{len(chunks)} 処理中 (サイズ: {len(chunk_text.encode('utf-8'))} bytes)")
                chunk_results = self._analyze_text_single(chunk_text, entities)
                
                # チャンクの結果の位置を全体テキストでの位置に調整
                for result in chunk_results:
                    result['start'] += len(text[:start_offset])
                    result['end'] += len(text[:start_offset])
                
                all_results.extend(chunk_results)
                
            except Exception as e:
                logger.error(f"チャンク {i+1} の処理でエラー: {e}")
                continue
        
        return sorted(all_results, key=lambda x: x['start'])
    
    def apply_masking(self, pdf_path: str, entities: List[Dict], masking_method: str = None) -> str:
        """PyMuPDFを使用してPDFにマスキングを適用"""
        if masking_method is None:
            masking_method = self._get_masking_method()
        
        # 出力ファイルパスを生成
        output_path = self._generate_output_path(pdf_path)
        
        try:
            if masking_method == "annotation":
                return self._apply_annotation_masking_pymupdf(pdf_path, entities, output_path)
            elif masking_method == "highlight":
                return self._apply_highlight_masking_pymupdf(pdf_path, entities, output_path)
            elif masking_method == "both":
                # まずハイライトを適用
                temp_path = output_path.replace('.pdf', '_temp.pdf')
                self._apply_highlight_masking_pymupdf(pdf_path, entities, temp_path)
                # 次に注釈を適用
                final_path = self._apply_annotation_masking_pymupdf(temp_path, entities, output_path)
                # 一時ファイルを削除
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return final_path
            else:
                raise ValueError(f"未対応のマスキング方式: {masking_method}")
        
        except Exception as e:
            logger.error(f"マスキング適用エラー: {e}")
            # フォールバック: 元のファイルをコピー
            shutil.copy2(pdf_path, output_path)
            logger.warning("マスキング処理に失敗しました。元のファイルをコピーしました。")
            return output_path
    
    def _get_masking_method(self) -> str:
        """マスキング方式を取得"""
        return self.config_manager.get_pdf_masking_method()
    
    def _generate_output_path(self, input_path: str) -> str:
        """出力ファイルパスを生成"""
        suffix = self.config_manager._safe_get_config('pdf_processing.output_suffix', '_masked')
        path_obj = Path(input_path)
        
        # 出力ディレクトリが指定されている場合は使用
        output_dir = self.config_manager.get_output_dir()
        if output_dir:
            output_dir_path = Path(output_dir)
            # 出力ディレクトリが存在しない場合は作成
            output_dir_path.mkdir(parents=True, exist_ok=True)
            return str(output_dir_path / f"{path_obj.stem}{suffix}{path_obj.suffix}")
        else:
            return str(path_obj.parent / f"{path_obj.stem}{suffix}{path_obj.suffix}")
    
    def _apply_annotation_masking_pymupdf(self, pdf_path: str, entities: List[Dict], output_path: str) -> str:
        """PyMuPDFを使用した注釈マスキング"""
        logger.info(f"PyMuPDF注釈マスキング適用中: {pdf_path}")
        
        try:
            doc = fitz.open(pdf_path)
            annotations_added = 0
            
            for entity in entities:
                coords = entity.get('coordinates', {})
                page_num = coords.get('page_number', 1) - 1  # 0-based index
                
                if page_num < len(doc):
                    page = doc[page_num]
                    
                    # 注釈の位置を計算
                    x0 = float(coords.get('x0', 50))
                    y0 = float(coords.get('y0', 700))
                    x1 = float(coords.get('x1', 200))
                    y1 = float(coords.get('y1', 715))
                    
                    # 座標の妥当性をチェック
                    if x0 >= x1 or y0 >= y1 or any(not float('-inf') < coord < float('inf') for coord in [x0, y0, x1, y1]):
                        logger.warning(f"無効な座標をスキップ: {coords}")
                        continue
                    
                    rect = fitz.Rect(x0, y0, x1, y1)
                    
                    # 矩形が有効かチェック
                    if rect.is_empty or rect.is_infinite:
                        logger.warning(f"無効な矩形をスキップ: {rect}")
                        continue
                    
                    try:
                        # 注釈の色を決定
                        color = self._get_annotation_color_pymupdf(entity['entity_type'])
                        
                        # 注釈内容を生成
                        content = self._generate_annotation_content(entity)
                        text_display_mode = self.config_manager.get_masking_text_display_mode()
                        
                        if text_display_mode == "silent":
                            # silentモードでは色のみの矩形注釈を作成
                            annot = page.add_square_annot(rect)
                            annot.set_colors(stroke=color, fill=[c * 0.3 for c in color])
                            annot.set_info(title="", content="")
                        else:
                            # フリーテキスト注釈を追加
                            annot = page.add_freetext_annot(
                                rect,
                                content,
                                fontsize=8,
                                text_color=color,
                                fill_color=[c * 0.3 for c in color]  # 薄い背景色
                            )
                            
                            # 注釈の設定
                            title = "個人情報検出" if text_display_mode == "verbose" else ""
                            annot.set_info(title=title, content=content)
                        
                        annot.update()
                        
                        annotations_added += 1
                        logger.debug(f"注釈を追加: {entity['entity_type']} - {entity['text']}")
                        
                    except Exception as e:
                        logger.warning(f"注釈追加でエラー: {e} (エンティティ: {entity['text']})")
                        continue
            
            # PDFを保存
            doc.save(output_path)
            doc.close()
            
            logger.info(f"PyMuPDF注釈マスキング完了: {output_path} ({annotations_added}件の注釈を追加)")
            return output_path
            
        except Exception as e:
            logger.error(f"PyMuPDF注釈マスキングエラー: {e}")
            raise
    
    def _apply_highlight_masking_pymupdf(self, pdf_path: str, entities: List[Dict], output_path: str) -> str:
        """PyMuPDFを使用したハイライトマスキング"""
        logger.info(f"PyMuPDFハイライトマスキング適用中: {pdf_path}")
        
        try:
            doc = fitz.open(pdf_path)
            highlights_added = 0
            
            for entity in entities:
                coords = entity.get('coordinates', {})
                page_num = coords.get('page_number', 1) - 1  # 0-based index
                
                if page_num < len(doc):
                    page = doc[page_num]
                    
                    # ハイライトの位置を計算
                    x0 = float(coords.get('x0', 50))
                    y0 = float(coords.get('y0', 700))
                    x1 = float(coords.get('x1', 200))
                    y1 = float(coords.get('y1', 715))
                    
                    # 座標の妥当性をチェック
                    if x0 >= x1 or y0 >= y1 or any(not float('-inf') < coord < float('inf') for coord in [x0, y0, x1, y1]):
                        logger.warning(f"無効な座標をスキップ: {coords}")
                        continue
                    
                    rect = fitz.Rect(x0, y0, x1, y1)
                    
                    # 矩形が有効かチェック
                    if rect.is_empty or rect.is_infinite:
                        logger.warning(f"無効な矩形をスキップ: {rect}")
                        continue
                    
                    try:
                        # ハイライトの色を決定
                        color = self._get_highlight_color_pymupdf(entity['entity_type'])
                        
                        # ハイライト注釈を追加
                        highlight = page.add_highlight_annot(rect)
                        highlight.set_colors(stroke=color)
                        
                        # 文字表示モードに応じてタイトルと内容を設定
                        text_display_mode = self.config_manager.get_masking_text_display_mode()
                        if text_display_mode == "silent":
                            highlight.set_info(title="", content="")
                        elif text_display_mode == "minimal":
                            type_names = {
                                'PERSON': '人名', 'LOCATION': '場所', 'DATE_TIME': '日時',
                                'PHONE_NUMBER': '電話番号', 'INDIVIDUAL_NUMBER': 'マイナンバー',
                                'YEAR': '年号', 'PROPER_NOUN': '固有名詞'
                            }
                            type_name = type_names.get(entity['entity_type'], entity['entity_type'])
                            highlight.set_info(title=type_name, content="")
                        else:  # verbose
                            highlight.set_info(title=f"個人情報: {entity['entity_type']}", content=entity['text'])
                        
                        highlight.update()
                        
                        highlights_added += 1
                        logger.debug(f"ハイライトを追加: {entity['entity_type']} - {entity['text']}")
                        
                    except Exception as e:
                        logger.warning(f"ハイライト追加でエラー: {e} (エンティティ: {entity['text']})")
                        continue
            
            # PDFを保存
            doc.save(output_path)
            doc.close()
            
            logger.info(f"PyMuPDFハイライトマスキング完了: {output_path} ({highlights_added}件のハイライトを追加)")
            return output_path
            
        except Exception as e:
            logger.error(f"PyMuPDFハイライトマスキングエラー: {e}")
            raise
    
    def _get_annotation_color_pymupdf(self, entity_type: str) -> List[float]:
        """エンティティタイプに応じたPyMuPDF用注釈色を取得"""
        color_mapping = {
            'PERSON': [1.0, 0.0, 0.0],        # 赤
            'LOCATION': [0.0, 1.0, 0.0],      # 緑
            'DATE_TIME': [0.0, 0.0, 1.0],     # 青
            'PHONE_NUMBER': [1.0, 1.0, 0.0],  # 黄
            'INDIVIDUAL_NUMBER': [1.0, 0.0, 1.0],  # マゼンタ
            'YEAR': [0.5, 0.0, 1.0],          # 紫
            'PROPER_NOUN': [1.0, 0.5, 0.0]    # オレンジ
        }
        return color_mapping.get(entity_type, [0.0, 0.0, 0.0])  # デフォルト: 黒
    
    def _get_highlight_color_pymupdf(self, entity_type: str) -> List[float]:
        """エンティティタイプに応じたPyMuPDF用ハイライト色を取得"""
        color_mapping = {
            'PERSON': [1.0, 0.8, 0.8],        # 薄い赤
            'LOCATION': [0.8, 1.0, 0.8],      # 薄い緑
            'DATE_TIME': [0.8, 0.8, 1.0],     # 薄い青
            'PHONE_NUMBER': [1.0, 1.0, 0.8],  # 薄い黄
            'INDIVIDUAL_NUMBER': [1.0, 0.8, 1.0],  # 薄いマゼンタ
            'YEAR': [0.9, 0.8, 1.0],          # 薄い紫
            'PROPER_NOUN': [1.0, 0.9, 0.8]    # 薄いオレンジ
        }
        return color_mapping.get(entity_type, [0.9, 0.9, 0.9])  # デフォルト: 薄い灰色
    
    def _generate_annotation_content(self, entity: Dict) -> str:
        """注釈内容を生成"""
        text_display_mode = self.config_manager.get_masking_text_display_mode()
        
        # silentモードの場合は空文字を返す
        if text_display_mode == "silent":
            return ""
        
        entity_type = entity['entity_type']
        confidence = entity.get('score', 0.0)
        text = entity.get('text', '')
        
        # エンティティタイプの日本語名
        type_names = {
            'PERSON': '人名',
            'LOCATION': '場所',
            'DATE_TIME': '日時',
            'PHONE_NUMBER': '電話番号',
            'INDIVIDUAL_NUMBER': 'マイナンバー',
            'YEAR': '年号',
            'PROPER_NOUN': '固有名詞'
        }
        
        type_name = type_names.get(entity_type, entity_type)
        
        if text_display_mode == "minimal":
            # 最小限の情報：エンティティタイプのみ
            return type_name
        elif text_display_mode == "verbose":
            # 詳細情報：エンティティタイプ + 信頼度
            content = f"【個人情報】{type_name}"
            
            if confidence > 0:
                content += f" (信頼度: {confidence:.1%})"
            
            # 設定によってはテキスト内容も含める
            annotation_settings = self.config_manager.get_pdf_annotation_settings()
            if annotation_settings.get('include_text', False):
                content += f"\nテキスト: {text[:20]}..."
            
            return content
        else:
            # 未知のモードの場合はverboseとして扱う
            logger.warning(f"未知の文字表示モード: {text_display_mode}. verboseとして扱います。")
            return f"【個人情報】{type_name}"
    
    def _create_backup(self, file_path: str) -> str:
        """ファイルのバックアップを作成"""
        if not self.config_manager._safe_get_config('pdf_processing.backup_enabled', False):
            return None
        
        backup_suffix = self.config_manager._safe_get_config('pdf_processing.backup_suffix', '_backup')
        path_obj = Path(file_path)
        backup_path = path_obj.parent / f"{path_obj.stem}{backup_suffix}{path_obj.suffix}"
        
        try:
            shutil.copy2(file_path, backup_path)
            logger.info(f"バックアップを作成: {backup_path}")
            return str(backup_path)
        except Exception as e:
            logger.warning(f"バックアップ作成に失敗: {e}")
            return None
    
    def _should_skip_file(self, file_path: str) -> bool:
        """ファイルをスキップすべきか判定"""
        file_exclusions = self.config_manager._safe_get_config('pdf_processing.exclusions.files', [])
        file_name = os.path.basename(file_path)
        
        for pattern in file_exclusions:
            if fnmatch.fnmatch(file_name, pattern):
                logger.debug(f"ファイル除外パターンにマッチ: {file_path}")
                return True
        
        return False
    
    def process_pdf_file(self, input_path: str, masking_method: str = None) -> Dict:
        """単一PDFファイルを処理"""
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"ファイルが見つかりません: {input_path}")
        
        if self._should_skip_file(input_path):
            logger.info(f"ファイルをスキップ: {input_path}")
            return {'input_file': input_path, 'skipped': True, 'reason': '除外パターンにマッチ'}
        
        logger.info(f"PDF処理開始: {input_path}")
        
        # バックアップ作成
        backup_path = self._create_backup(input_path)
        
        detected_entities = []
        
        try:
            # 個人情報を検出
            entities = self.analyze_pdf(input_path)
            
            # マスキングを適用
            output_path = self.apply_masking(input_path, entities, masking_method)
            
            detected_entities = entities
            
            logger.info(f"PDF処理完了: {output_path} ({len(detected_entities)}件の個人情報を処理)")
            
        except Exception as e:
            logger.error(f"PDF処理エラー: {e}")
            raise
        
        # 統計情報を作成
        summary = {
            'input_file': input_path,
            'output_file': output_path,
            'backup_file': backup_path,
            'total_entities_found': len(detected_entities),
            'entities_by_type': {},
            'detected_entities': detected_entities if self.config_manager.should_include_detected_text_in_pdf_report() else [],
            'processing_time': (datetime.now() - datetime.now()).total_seconds()
        }
        
        for entity in detected_entities:
            entity_type = entity['entity_type']
            if entity_type not in summary['entities_by_type']:
                summary['entities_by_type'][entity_type] = 0
            summary['entities_by_type'][entity_type] += 1
        
        # 統計情報を更新
        self.processing_stats['files_processed'] += 1
        self.processing_stats['total_entities_found'] += len(detected_entities)
        for entity_type, count in summary['entities_by_type'].items():
            if entity_type not in self.processing_stats['entities_by_type']:
                self.processing_stats['entities_by_type'][entity_type] = 0
            self.processing_stats['entities_by_type'][entity_type] += count
        
        return summary
    
    def process_files(self, path: str, masking_method: str = None) -> List[Dict]:
        """ファイルまたはフォルダを処理"""
        results = []
        
        # 読み取りモードかどうかをチェック
        if self.config_manager.is_read_mode_enabled():
            return self._process_files_read_mode(path)
        
        if os.path.isfile(path):
            # 単一ファイルの処理
            if path.lower().endswith('.pdf'):
                try:
                    result = self.process_pdf_file(path, masking_method)
                    results.append(result)
                except Exception as e:
                    logger.error(f"ファイル処理エラー ({path}): {e}")
                    results.append({'input_file': path, 'error': str(e)})
            else:
                logger.warning(f"サポートされていないファイル形式: {path}")
        
        elif os.path.isdir(path):
            # フォルダ内のPDFファイルを処理
            import glob
            pdf_files = []
            pdf_files.extend(glob.glob(os.path.join(path, '*.pdf')))
            pdf_files.extend(glob.glob(os.path.join(path, '**', '*.pdf'), recursive=True))
            
            logger.info(f"フォルダ内で見つかったPDFファイル: {len(pdf_files)}個")
            
            for file_path in pdf_files:
                try:
                    result = self.process_pdf_file(file_path, masking_method)
                    results.append(result)
                except Exception as e:
                    logger.error(f"ファイル処理エラー ({file_path}): {e}")
                    results.append({'input_file': file_path, 'error': str(e)})
        
        else:
            raise ValueError(f"存在しないパスです: {path}")
        
        # レポート生成
        report_file = self._generate_report(results)
        if report_file:
            logger.info(f"処理レポート: {report_file}")
        
        return results
    
    def _process_files_read_mode(self, path: str) -> List[Dict]:
        """読み取りモードでファイルを処理"""
        results = []
        
        if os.path.isfile(path):
            # 単一ファイルの読み取り
            if path.lower().endswith('.pdf'):
                try:
                    result = self._read_pdf_file(path)
                    results.append(result)
                except Exception as e:
                    logger.error(f"ファイル読み取りエラー ({path}): {e}")
                    results.append({'input_file': path, 'error': str(e)})
            else:
                logger.warning(f"サポートされていないファイル形式: {path}")
        
        elif os.path.isdir(path):
            # フォルダ内のPDFファイルを読み取り
            import glob
            pdf_files = []
            pdf_files.extend(glob.glob(os.path.join(path, '*.pdf')))
            pdf_files.extend(glob.glob(os.path.join(path, '**', '*.pdf'), recursive=True))
            
            logger.info(f"読み取り対象PDFファイル: {len(pdf_files)}個")
            
            for file_path in pdf_files:
                try:
                    result = self._read_pdf_file(file_path)
                    results.append(result)
                except Exception as e:
                    logger.error(f"ファイル読み取りエラー ({file_path}): {e}")
                    results.append({'input_file': file_path, 'error': str(e)})
        
        else:
            raise ValueError(f"存在しないパスです: {path}")
        
        return results
    
    def _read_pdf_file(self, pdf_path: str) -> Dict:
        """単一PDFファイルから注釈を読み取り"""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"ファイルが見つかりません: {pdf_path}")
        
        if self._should_skip_file(pdf_path):
            logger.info(f"ファイルをスキップ: {pdf_path}")
            return {'input_file': pdf_path, 'skipped': True, 'reason': '除外パターンにマッチ'}
        
        logger.info(f"PDF注釈読み取り開始: {pdf_path}")
        
        try:
            # 注釈を読み取り
            annotations = self.read_pdf_annotations(pdf_path)
            
            # レポート生成
            report_file = None
            if self.config_manager.should_generate_read_report():
                report_file = self._generate_annotations_report(annotations, pdf_path)
            
            logger.info(f"PDF注釈読み取り完了: {pdf_path} ({len(annotations)}件の注釈)")
            
            return {
                'input_file': pdf_path,
                'total_annotations': len(annotations),
                'annotations_by_type': self._count_annotations_by_type(annotations),
                'annotations_by_page': self._count_annotations_by_page(annotations),
                'annotations': annotations,
                'report_file': report_file
            }
            
        except Exception as e:
            logger.error(f"PDF読み取りエラー: {e}")
            raise
    
    def _count_annotations_by_type(self, annotations: List[Dict]) -> Dict[str, int]:
        """注釈をタイプ別にカウント"""
        counts = {}
        for annotation in annotations:
            annot_type = annotation.get('annotation_type', 'Unknown')
            counts[annot_type] = counts.get(annot_type, 0) + 1
        return counts
    
    def _count_annotations_by_page(self, annotations: List[Dict]) -> Dict[int, int]:
        """注釈をページ別にカウント"""
        counts = {}
        for annotation in annotations:
            page_num = annotation.get('coordinates', {}).get('page_number', 1)
            counts[page_num] = counts.get(page_num, 0) + 1
        return counts
    
    def read_pdf_annotations(self, pdf_path: str) -> List[Dict]:
        """PDFから既存の注釈・ハイライトを読み取る"""
        logger.info(f"PDF注釈読み取り開始: {pdf_path}")
        
        try:
            doc = fitz.open(pdf_path)
            all_annotations = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                annotations = page.annots()
                
                for annot in annotations:
                    try:
                        annot_info = self._extract_annotation_info(annot, page_num + 1, page)
                        if annot_info:
                            all_annotations.append(annot_info)
                    except Exception as e:
                        logger.warning(f"注釈読み取りエラー (ページ{page_num + 1}): {e}")
                        continue
            
            doc.close()
            logger.info(f"PDF注釈読み取り完了: {len(all_annotations)}件の注釈を検出")
            return all_annotations
            
        except Exception as e:
            logger.error(f"PDF注釈読み取りエラー: {e}")
            raise
    
    def _extract_annotation_info(self, annot, page_number: int, page) -> Dict:
        """注釈から詳細情報を抽出"""
        try:
            # 注釈の基本情報
            rect = annot.rect
            annot_type = annot.type[1]  # 注釈タイプ名
            
            # 座標情報
            coordinates = {
                'page_number': page_number,
                'x0': float(rect.x0),
                'y0': float(rect.y0),
                'x1': float(rect.x1),
                'y1': float(rect.y1),
                'width': float(rect.width),
                'height': float(rect.height)
            }
            
            # 注釈内容とタイトル
            content = annot.info.get('content', '')
            title = annot.info.get('title', '')
            
            # カバーされているテキストを抽出
            covered_text = self._extract_covered_text(rect, page)
            
            # 色情報
            color_info = self._extract_annotation_colors(annot)
            
            # 透明度情報
            opacity = self._extract_annotation_opacity(annot)
            
            annotation_info = {
                'annotation_type': annot_type,
                'coordinates': coordinates,
                'covered_text': covered_text,
                'title': title,
                'content': content,
                'color_info': color_info,
                'opacity': opacity,
                'creation_date': annot.info.get('creationDate', ''),
                'modification_date': annot.info.get('modDate', ''),
                'author': annot.info.get('subject', '')
            }
            
            return annotation_info
            
        except Exception as e:
            logger.debug(f"注釈情報抽出エラー: {e}")
            return None
    
    def _extract_covered_text(self, rect: fitz.Rect, page) -> str:
        """注釈がカバーしているテキストを抽出"""
        try:
            # 注釈の矩形領域内のテキストを取得
            text_instances = page.get_text("words", clip=rect)
            if text_instances:
                words = [word[4] for word in text_instances]  # word[4] is the text
                return ' '.join(words)
            
            # フォールバック: より広い範囲で検索
            expanded_rect = fitz.Rect(
                rect.x0 - 5, rect.y0 - 5, 
                rect.x1 + 5, rect.y1 + 5
            )
            text_instances = page.get_text("words", clip=expanded_rect)
            if text_instances:
                words = [word[4] for word in text_instances]
                return ' '.join(words)
            
            return ""
            
        except Exception as e:
            logger.debug(f"カバーテキスト抽出エラー: {e}")
            return ""
    
    def _extract_annotation_colors(self, annot) -> Dict:
        """注釈の色情報を抽出"""
        try:
            color_info = {}
            
            # ストローク色（線色）
            stroke_color = annot.colors.get('stroke')
            if stroke_color:
                color_info['stroke_color'] = {
                    'rgb': list(stroke_color),
                    'hex': self._rgb_to_hex(stroke_color)
                }
            
            # フィル色（塗りつぶし色）
            fill_color = annot.colors.get('fill')
            if fill_color:
                color_info['fill_color'] = {
                    'rgb': list(fill_color),
                    'hex': self._rgb_to_hex(fill_color)
                }
            
            return color_info
            
        except Exception as e:
            logger.debug(f"色情報抽出エラー: {e}")
            return {}
    
    def _rgb_to_hex(self, rgb_values: List[float]) -> str:
        """RGB値を16進数色コードに変換"""
        try:
            if len(rgb_values) >= 3:
                r = int(rgb_values[0] * 255)
                g = int(rgb_values[1] * 255)
                b = int(rgb_values[2] * 255)
                return f"#{r:02x}{g:02x}{b:02x}"
            return "#000000"
        except:
            return "#000000"
    
    def _extract_annotation_opacity(self, annot) -> float:
        """注釈の透明度を抽出"""
        try:
            # PyMuPDFではopacityプロパティから取得
            opacity = getattr(annot, 'opacity', None)
            if opacity is not None:
                return float(opacity)
            
            # フォールバック: カスタム属性から取得
            for key, value in annot.info.items():
                if 'opacity' in key.lower() and isinstance(value, (int, float)):
                    return float(value)
            
            return 1.0  # デフォルト: 完全不透明
            
        except Exception as e:
            logger.debug(f"透明度抽出エラー: {e}")
            return 1.0
    
    
    def _generate_annotations_report(self, annotations: List[Dict], pdf_path: str) -> str:
        """読み取った注釈のレポートを生成"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"annotations_report_{timestamp}.json"
        
        # 出力ディレクトリが指定されている場合は使用
        output_dir = self.config_manager.get_output_dir()
        if output_dir:
            output_dir_path = Path(output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)
            report_filename = str(output_dir_path / report_filename)
        
        try:
            report_data = {
                'pdf_file': pdf_path,
                'scan_date': datetime.now().isoformat(),
                'total_annotations': len(annotations),
                'annotations_by_type': {},
                'annotations_by_page': {},
                'annotations': annotations
            }
            
            # 統計情報を計算
            for annotation in annotations:
                # タイプ別統計
                annot_type = annotation['annotation_type']
                if annot_type not in report_data['annotations_by_type']:
                    report_data['annotations_by_type'][annot_type] = 0
                report_data['annotations_by_type'][annot_type] += 1
                
                # ページ別統計
                page_num = annotation['coordinates']['page_number']
                if page_num not in report_data['annotations_by_page']:
                    report_data['annotations_by_page'][page_num] = 0
                report_data['annotations_by_page'][page_num] += 1
            
            with open(report_filename, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"注釈レポートを生成: {report_filename}")
            return report_filename
            
        except Exception as e:
            logger.error(f"注釈レポート生成エラー: {e}")
            return None

    def _generate_report(self, results: List[Dict]) -> str:
        """処理結果のレポートを生成"""
        if not self.config_manager._safe_get_config('pdf_processing.report.generate_report', False):
            return None
        
        report_format = self.config_manager._safe_get_config('pdf_processing.report.format', 'json')
        report_prefix = self.config_manager._safe_get_config('pdf_processing.report.prefix', 'pdf_report')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{report_prefix}_{timestamp}.{report_format}"
        
        # 出力ディレクトリが指定されている場合は使用
        output_dir = self.config_manager.get_output_dir()
        if output_dir:
            output_dir_path = Path(output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)
            report_filename = str(output_dir_path / report_filename)
        
        try:
            if report_format == 'json':
                report_data = {
                    'processing_stats': self.processing_stats,
                    'file_results': results,
                    'config_summary': {
                        'enabled_entities': self.config_manager.get_enabled_entities(),
                        'thresholds': {entity: self.config_manager.get_threshold(entity) for entity in self.config_manager.get_enabled_entities()},
                        'masking_method': self._get_masking_method()
                    }
                }
                with open(report_filename, 'w', encoding='utf-8') as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            elif report_format == 'csv':
                import csv
                with open(report_filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['File', 'Entities Found', 'Status', 'Entity Types'])
                    for result in results:
                        if 'error' not in result and 'skipped' not in result:
                            entity_types = ', '.join(f"{k}:{v}" for k, v in result.get('entities_by_type', {}).items())
                            writer.writerow([result['input_file'], result['total_entities_found'], 'Success', entity_types])
                        else:
                            status = 'Error' if 'error' in result else 'Skipped'
                            writer.writerow([result['input_file'], 0, status, ''])
            
            logger.info(f"レポートを生成: {report_filename}")
            return report_filename
        
        except Exception as e:
            logger.error(f"レポート生成でエラー: {e}")
            return None


@click.command()
@click.argument('path', type=click.Path(exists=True), required=True)
# 基本設定オプション
@click.option('--config', '-c', type=click.Path(exists=True), help='YAML設定ファイルのパス')
@click.option('--verbose', '-v', is_flag=True, help='詳細なログを表示')
@click.option('--output-dir', '-o', type=click.Path(), help='出力ディレクトリ')
# モード選択オプション
@click.option('--read-mode', '-r', is_flag=True, help='読み取りモード: 既存の注釈・ハイライトを読み取り')
@click.option('--read-report', is_flag=True, default=True, help='読み取りレポートを生成 (デフォルト: True)')
# マスキング設定オプション  
@click.option('--masking-method', type=click.Choice(['annotation', 'highlight', 'both']), 
              help='マスキング方式 (annotation: 注釈, highlight: ハイライト, both: 両方)')
@click.option('--masking-text-mode', type=click.Choice(['silent', 'minimal', 'verbose']), 
              help='マスキング文字表示モード (silent: 文字なし, minimal: 最小限, verbose: 詳細)')
# 処理設定オプション
@click.option('--spacy-model', '-m', type=str, help='使用するspaCyモデル名 (ja_core_news_sm, ja_core_news_md, ja_ginza, ja_ginza_electra)')
@click.option('--deduplication-mode', type=click.Choice(['score', 'wider_range', 'narrower_range', 'entity_type']), 
              help='重複除去モード (score: スコア優先, wider_range: 広い範囲優先, narrower_range: 狭い範囲優先, entity_type: エンティティタイプ優先)')
@click.option('--deduplication-overlap-mode', type=click.Choice(['contain_only', 'partial_overlap']),
              help='重複判定モード (contain_only: 包含関係のみ, partial_overlap: 一部重なりも含む)')
def main(path, config, verbose, output_dir, read_mode, read_report, masking_method, masking_text_mode, spacy_model, deduplication_mode, deduplication_overlap_mode):
    """PyMuPDF版 PDF個人情報検出・マスキング・読み取りツール
    
    [通常モード] PDFファイルから個人情報を検出し、高性能なPyMuPDFライブラリで注釈またはハイライトでマスキングします。
    [読み取りモード] 既存のPDF注釈・ハイライトを読み取り、詳細情報を抽出します。
    
    詳細な設定はYAML設定ファイルで指定してください。
    
    PATH: 処理するPDFファイルまたはフォルダのパス
    """
    
    # 引数を辞書に変換
    args_dict = {
        'verbose': verbose,
        'output_dir': output_dir,
        'read_mode': read_mode,
        'read_report': read_report,
        'pdf_masking_method': masking_method,
        'masking_text_mode': masking_text_mode,
        'spacy_model': spacy_model,
        'deduplication_mode': deduplication_mode,
        'deduplication_overlap_mode': deduplication_overlap_mode
    }
    
    # ConfigManagerを初期化
    config_manager = ConfigManager(config_file=config, args=args_dict)
    
    # ログレベルを設定
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # PDFプロセッサーを初期化
    processor = PDFPresidioProcessor(config_manager)
    
    try:
        # 読み取りモードかマスキングモードかで処理を分岐
        if config_manager.is_read_mode_enabled():
            # 読み取りモード
            results = processor.process_files(path)
            
            # 読み取り結果の表示
            click.echo(f"\n=== PDF注釈読み取り結果 ===")
            total_files = len(results)
            successful_files = len([r for r in results if 'error' not in r and 'skipped' not in r])
            skipped_files = len([r for r in results if 'skipped' in r])
            error_files = len([r for r in results if 'error' in r])
            total_annotations = sum(r.get('total_annotations', 0) for r in results if 'error' not in r and 'skipped' not in r)
            
            click.echo(f"読み取りファイル数: {successful_files}/{total_files}")
            if skipped_files > 0:
                click.echo(f"スキップファイル数: {skipped_files}")
            if error_files > 0:
                click.echo(f"エラーファイル数: {error_files}")
            click.echo(f"読み取った注釈総数: {total_annotations}")
            
            for result in results:
                if 'error' in result:
                    click.echo(f"\n❌ エラー: {result['input_file']}")
                    click.echo(f"   {result['error']}")
                elif 'skipped' in result:
                    click.echo(f"\n[スキップ] {result['input_file']}")
                    click.echo(f"   理由: {result.get('reason', '不明')}")
                else:
                    click.echo(f"\n📖 [読み取り成功] {result['input_file']}")
                    click.echo(f"   注釈数: {result['total_annotations']}")
                    if result.get('report_file'):
                        click.echo(f"   レポート: {result['report_file']}")
                    
                    if result.get('annotations_by_type'):
                        click.echo("   タイプ別:")
                        for annot_type, count in result['annotations_by_type'].items():
                            click.echo(f"     {annot_type}: {count}件")
                    
                    if result.get('annotations_by_page'):
                        page_info = [f"ページ{page}: {count}件" for page, count in result['annotations_by_page'].items()]
                        click.echo(f"   ページ別: {', '.join(page_info)}")
                    
                    # 詳細表示（--verboseの場合）
                    if verbose and result.get('annotations'):
                        click.echo("   注釈詳細:")
                        for i, annotation in enumerate(result['annotations'][:5]):  # 最初の5件のみ表示
                            click.echo(f"     {i+1}. {annotation.get('annotation_type', 'Unknown')}")
                            click.echo(f"        場所: ページ{annotation.get('coordinates', {}).get('page_number', '?')}")
                            click.echo(f"        テキスト: {annotation.get('covered_text', '')[:50]}...")
                            if annotation.get('color_info'):
                                colors = []
                                if 'stroke_color' in annotation['color_info']:
                                    colors.append(f"線: {annotation['color_info']['stroke_color'].get('hex', '#000000')}")
                                if 'fill_color' in annotation['color_info']:
                                    colors.append(f"塗り: {annotation['color_info']['fill_color'].get('hex', '#000000')}")
                                if colors:
                                    click.echo(f"        色: {', '.join(colors)}")
                            click.echo(f"        透明度: {annotation.get('opacity', 1.0)}")
                        
                        if len(result['annotations']) > 5:
                            click.echo(f"     ... および他{len(result['annotations']) - 5}件")
        else:
            # マスキングモード
            masking_method = config_manager.get_pdf_masking_method()
            results = processor.process_files(path, masking_method)
            
            # マスキング結果の表示
            click.echo(f"\n=== PyMuPDF PDF処理結果 ===")
            total_files = len(results)
            successful_files = len([r for r in results if 'error' not in r and 'skipped' not in r])
            skipped_files = len([r for r in results if 'skipped' in r])
            error_files = len([r for r in results if 'error' in r])
            total_entities = sum(r.get('total_entities_found', 0) for r in results if 'error' not in r and 'skipped' not in r)
            
            click.echo(f"処理ファイル数: {successful_files}/{total_files}")
            if skipped_files > 0:
                click.echo(f"スキップファイル数: {skipped_files}")
            if error_files > 0:
                click.echo(f"エラーファイル数: {error_files}")
            click.echo(f"検出された個人情報総数: {total_entities}")
            
            # 有効なエンティティタイプを表示
            enabled_entities = config_manager.get_enabled_entities()
            click.echo(f"検出対象: {', '.join(enabled_entities)}")
            click.echo(f"マスキング方式: {masking_method or processor._get_masking_method()}")
            click.echo(f"文字表示モード: {masking_text_mode or config_manager.get_masking_text_display_mode()}")
            
            for result in results:
                if 'error' in result:
                    click.echo(f"\n❌ エラー: {result['input_file']}")
                    click.echo(f"   {result['error']}")
                elif 'skipped' in result:
                    click.echo(f"\n[スキップ] {result['input_file']}")
                    click.echo(f"   理由: {result.get('reason', '不明')}")
                else:
                    click.echo(f"\n✅ [成功] {result['input_file']}")
                    click.echo(f"   出力: {result['output_file']}")
                    if result.get('backup_file'):
                        click.echo(f"   バックアップ: {result['backup_file']}")
                    click.echo(f"   検出数: {result['total_entities_found']}")
                    if result['entities_by_type']:
                        click.echo("   種類別:")
                        for entity_type, count in result['entities_by_type'].items():
                            click.echo(f"     {entity_type}: {count}件")
    
    except KeyboardInterrupt:
        click.echo("\n処理が中断されました")
    except Exception as e:
        logger.error(f"処理中にエラーが発生しました: {e}")
        click.echo(f"エラー: {e}")


if __name__ == "__main__":
    main()