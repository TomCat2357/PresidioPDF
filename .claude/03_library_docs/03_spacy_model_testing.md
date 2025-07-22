# spaCy 日本語モデル統合・テスト戦略

## 概要
PresidioPDF プロジェクトにおける spaCy 日本語モデルの統合、テスト、最適化戦略を定義する。異なるモデルサイズ（sm/md/lg/trf）の特性を理解し、用途に応じた最適な選択と実装パターンを提供する。

## spaCy 日本語モデル概要

### 利用可能モデル
```python
# サポートモデル一覧
SUPPORTED_MODELS = {
    "ja_core_news_sm": {
        "size": "13MB",
        "performance": "軽量・高速",
        "accuracy": "基本",
        "use_case": "開発・テスト環境",
        "ner_entities": ["PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT"],
        "pipeline": ["tok2vec", "tagger", "parser", "ner", "attribute_ruler", "lemmatizer"]
    },
    "ja_core_news_md": {
        "size": "40MB", 
        "performance": "バランス",
        "accuracy": "中程度",
        "use_case": "本番環境推奨",
        "ner_entities": ["PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT"],
        "pipeline": ["tok2vec", "tagger", "parser", "ner", "attribute_ruler", "lemmatizer"],
        "word_vectors": True
    },
    "ja_core_news_lg": {
        "size": "540MB",
        "performance": "高精度・重い",
        "accuracy": "高精度",
        "use_case": "高精度要求時",
        "ner_entities": ["PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT"],
        "pipeline": ["tok2vec", "tagger", "parser", "ner", "attribute_ruler", "lemmatizer"],
        "word_vectors": True,
        "vector_size": 300
    },
    "ja_core_news_trf": {
        "size": "438MB",
        "performance": "最高精度・最重い",
        "accuracy": "最高",
        "use_case": "最高精度必須時",
        "ner_entities": ["PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT"],
        "pipeline": ["transformer", "tagger", "parser", "ner", "attribute_ruler", "lemmatizer"],
        "transformer": "cl-tohoku/bert-base-japanese-v2"
    }
}
```

## モデル選択戦略

### パフォーマンス vs 精度トレードオフ
```python
class SpacyModelSelector:
    """spaCy モデル選択支援クラス"""
    
    def __init__(self):
        self.model_specs = SUPPORTED_MODELS
        self.benchmark_results = self._load_benchmark_results()
    
    def recommend_model(
        self, 
        use_case: str,
        performance_priority: str = "balanced",
        memory_limit: str = None,
        gpu_available: bool = False
    ) -> str:
        """用途に応じたモデル推奨"""
        
        recommendations = {
            "development": {
                "model": "ja_core_news_sm",
                "reason": "開発効率重視、高速起動"
            },
            "testing": {
                "model": "ja_core_news_sm", 
                "reason": "テスト実行時間短縮"
            },
            "production_standard": {
                "model": "ja_core_news_md",
                "reason": "精度とパフォーマンスのバランス"
            },
            "production_high_accuracy": {
                "model": "ja_core_news_lg" if not gpu_available else "ja_core_news_trf",
                "reason": "高精度要求、十分なリソース"
            },
            "batch_processing": {
                "model": "ja_core_news_trf" if gpu_available else "ja_core_news_lg",
                "reason": "バッチ処理では処理時間より精度重視"
            }
        }
        
        if memory_limit:
            memory_constraints = {
                "low": "ja_core_news_sm",      # < 100MB
                "medium": "ja_core_news_md",   # < 200MB  
                "high": "ja_core_news_lg"      # < 1GB
            }
            
            recommended = recommendations.get(use_case, {})
            if memory_limit in memory_constraints:
                constrained_model = memory_constraints[memory_limit]
                
                # より小さいモデルが推奨された場合は制約を適用
                current_size = self._get_model_size(recommended.get("model", ""))
                constraint_size = self._get_model_size(constrained_model)
                
                if current_size > constraint_size:
                    recommended["model"] = constrained_model
                    recommended["reason"] += f" (メモリ制約: {memory_limit})"
        
        return recommendations.get(use_case, recommendations["production_standard"])
    
    def _get_model_size(self, model_name: str) -> int:
        """モデルサイズを数値で取得"""
        size_str = self.model_specs.get(model_name, {}).get("size", "0MB")
        return int(size_str.replace("MB", "").replace("GB", "000"))
    
    def _load_benchmark_results(self) -> Dict[str, Any]:
        """ベンチマーク結果読み込み"""
        return {
            "processing_speed": {
                "ja_core_news_sm": {"docs_per_sec": 850, "tokens_per_sec": 15000},
                "ja_core_news_md": {"docs_per_sec": 420, "tokens_per_sec": 8500},
                "ja_core_news_lg": {"docs_per_sec": 180, "tokens_per_sec": 3200},
                "ja_core_news_trf": {"docs_per_sec": 45, "tokens_per_sec": 850}
            },
            "memory_usage": {
                "ja_core_news_sm": {"loading": "45MB", "processing": "85MB"},
                "ja_core_news_md": {"loading": "120MB", "processing": "180MB"},
                "ja_core_news_lg": {"loading": "620MB", "processing": "850MB"},
                "ja_core_news_trf": {"loading": "520MB", "processing": "1.2GB"}
            }
        }
```

## モデル精度検証システム

### NER精度テストスイート
```python
class SpacyNERAccuracyTester:
    """spaCy NER精度テストクラス"""
    
    def __init__(self, model_name: str):
        import spacy
        self.model_name = model_name
        self.nlp = spacy.load(model_name)
        
        # 日本語個人情報テストデータ
        self.test_dataset = self._create_test_dataset()
    
    def _create_test_dataset(self) -> List[Dict[str, Any]]:
        """日本語個人情報テストデータセット作成"""
        return [
            {
                "text": "私の名前は田中太郎です。電話番号は03-1234-5678で、住所は東京都渋谷区恵比寿1-2-3です。",
                "expected_entities": [
                    {"start": 5, "end": 9, "label": "PERSON", "text": "田中太郎"},
                    {"start": 26, "end": 35, "label": "PHONE", "text": "03-1234-5678"},  # カスタム
                    {"start": 40, "end": 55, "label": "LOC", "text": "東京都渋谷区恵比寿1-2-3"}
                ]
            },
            {
                "text": "佐藤花子さんが株式会社テストに勤務しています。連絡先：hanako@test.co.jp",
                "expected_entities": [
                    {"start": 0, "end": 4, "label": "PERSON", "text": "佐藤花子"},
                    {"start": 7, "end": 15, "label": "ORG", "text": "株式会社テスト"},
                    {"start": 25, "end": 41, "label": "EMAIL", "text": "hanako@test.co.jp"}
                ]
            },
            {
                "text": "マイナンバー：1234-5678-9012、郵便番号：123-4567",
                "expected_entities": [
                    {"start": 7, "end": 21, "label": "MY_NUMBER", "text": "1234-5678-9012"},
                    {"start": 27, "end": 35, "label": "POSTAL_CODE", "text": "123-4567"}
                ]
            },
            {
                "text": "生年月日：1990年5月15日、会員番号：ABC123456",
                "expected_entities": [
                    {"start": 5, "end": 15, "label": "DATE", "text": "1990年5月15日"},
                    {"start": 21, "end": 30, "label": "ID", "text": "ABC123456"}
                ]
            }
        ]
    
    def evaluate_model_accuracy(self) -> Dict[str, float]:
        """モデル精度評価実行"""
        
        total_expected = 0
        total_predicted = 0
        true_positives = 0
        
        results_by_entity = {}
        
        for test_case in self.test_dataset:
            text = test_case["text"]
            expected = test_case["expected_entities"]
            
            # spaCy分析実行
            doc = self.nlp(text)
            predicted = [
                {
                    "start": ent.start_char,
                    "end": ent.end_char, 
                    "label": ent.label_,
                    "text": ent.text
                }
                for ent in doc.ents
            ]
            
            # マッチング評価
            tp, fp, fn = self._evaluate_predictions(expected, predicted)
            
            true_positives += tp
            total_predicted += len(predicted)
            total_expected += len(expected)
            
            # エンティティタイプ別評価
            for entity in expected:
                entity_type = entity["label"]
                if entity_type not in results_by_entity:
                    results_by_entity[entity_type] = {"tp": 0, "fp": 0, "fn": 0}
                
                found = any(
                    pred["start"] == entity["start"] and 
                    pred["end"] == entity["end"] and
                    pred["label"] == entity["label"]
                    for pred in predicted
                )
                
                if found:
                    results_by_entity[entity_type]["tp"] += 1
                else:
                    results_by_entity[entity_type]["fn"] += 1
        
        # 全体精度計算
        precision = true_positives / total_predicted if total_predicted > 0 else 0
        recall = true_positives / total_expected if total_expected > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # エンティティタイプ別精度
        entity_scores = {}
        for entity_type, scores in results_by_entity.items():
            tp, fp, fn = scores["tp"], scores["fp"], scores["fn"]
            entity_precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            entity_recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            entity_f1 = 2 * (entity_precision * entity_recall) / (entity_precision + entity_recall) if (entity_precision + entity_recall) > 0 else 0
            
            entity_scores[entity_type] = {
                "precision": entity_precision,
                "recall": entity_recall,
                "f1_score": entity_f1
            }
        
        return {
            "overall": {
                "precision": precision,
                "recall": recall,
                "f1_score": f1_score,
                "model": self.model_name
            },
            "by_entity": entity_scores,
            "raw_counts": {
                "true_positives": true_positives,
                "total_predicted": total_predicted,
                "total_expected": total_expected
            }
        }
    
    def _evaluate_predictions(
        self, 
        expected: List[Dict], 
        predicted: List[Dict]
    ) -> Tuple[int, int, int]:
        """予測結果評価"""
        
        expected_set = set()
        predicted_set = set()
        
        for entity in expected:
            expected_set.add((entity["start"], entity["end"], entity["label"]))
        
        for entity in predicted:
            predicted_set.add((entity["start"], entity["end"], entity["label"]))
        
        true_positives = len(expected_set & predicted_set)
        false_positives = len(predicted_set - expected_set)
        false_negatives = len(expected_set - predicted_set)
        
        return true_positives, false_positives, false_negatives
```

## パフォーマンステスト

### 処理速度ベンチマーク
```python
class SpacyPerformanceBenchmark:
    """spaCy パフォーマンステストクラス"""
    
    def __init__(self):
        self.models_to_test = [
            "ja_core_news_sm",
            "ja_core_news_md", 
            "ja_core_news_lg",
            "ja_core_news_trf"
        ]
        
        # テストデータ生成
        self.test_corpus = self._generate_test_corpus()
    
    def _generate_test_corpus(self) -> List[str]:
        """テスト用日本語コーパス生成"""
        base_texts = [
            "私の名前は田中太郎です。東京都渋谷区に住んでいます。",
            "佐藤花子さんは株式会社テストで働いています。",
            "連絡先は03-1234-5678です。メールアドレスはtest@example.comです。",
            "マイナンバーは1234-5678-9012で、郵便番号は123-4567です。",
            "生年月日は1990年5月15日で、会員番号はABC123456です。"
        ]
        
        # 異なる長さのテキストを生成
        test_corpus = []
        
        # 短文（~50文字）
        test_corpus.extend(base_texts * 20)
        
        # 中文（~200文字）
        medium_texts = [" ".join(base_texts[:3]) for _ in range(15)]
        test_corpus.extend(medium_texts)
        
        # 長文（~500文字）
        long_texts = [" ".join(base_texts) for _ in range(10)]
        test_corpus.extend(long_texts)
        
        return test_corpus
    
    def benchmark_all_models(self) -> Dict[str, Any]:
        """全モデルのベンチマーク実行"""
        
        results = {}
        
        for model_name in self.models_to_test:
            try:
                print(f"Testing {model_name}...")
                model_results = self._benchmark_single_model(model_name)
                results[model_name] = model_results
                
            except Exception as e:
                print(f"Error testing {model_name}: {e}")
                results[model_name] = {"error": str(e)}
        
        return self._analyze_benchmark_results(results)
    
    def _benchmark_single_model(self, model_name: str) -> Dict[str, Any]:
        """単一モデルのベンチマーク"""
        import spacy
        import time
        import psutil
        import gc
        
        # メモリ測定開始
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # モデル読み込み時間測定
        start_time = time.time()
        nlp = spacy.load(model_name)
        loading_time = time.time() - start_time
        
        memory_after_loading = process.memory_info().rss / 1024 / 1024  # MB
        
        # 処理速度測定
        processing_times = []
        total_tokens = 0
        
        start_time = time.time()
        
        for text in self.test_corpus:
            text_start = time.time()
            doc = nlp(text)
            text_time = time.time() - text_start
            
            processing_times.append(text_time)
            total_tokens += len(doc)
        
        total_processing_time = time.time() - start_time
        memory_peak = process.memory_info().rss / 1024 / 1024  # MB
        
        # メモリクリーンアップ
        del nlp
        gc.collect()
        
        # 統計計算
        avg_processing_time = sum(processing_times) / len(processing_times)
        docs_per_second = len(self.test_corpus) / total_processing_time
        tokens_per_second = total_tokens / total_processing_time
        
        return {
            "loading_time": loading_time,
            "total_processing_time": total_processing_time,
            "avg_processing_time": avg_processing_time,
            "docs_per_second": docs_per_second,
            "tokens_per_second": tokens_per_second,
            "total_tokens": total_tokens,
            "memory_usage": {
                "before_loading": memory_before,
                "after_loading": memory_after_loading,
                "peak_usage": memory_peak,
                "loading_overhead": memory_after_loading - memory_before,
                "peak_overhead": memory_peak - memory_before
            },
            "processing_times": {
                "min": min(processing_times),
                "max": max(processing_times),
                "median": sorted(processing_times)[len(processing_times) // 2]
            }
        }
    
    def _analyze_benchmark_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """ベンチマーク結果分析"""
        
        analysis = {
            "summary": {},
            "recommendations": {},
            "detailed_results": results
        }
        
        # 性能サマリー作成
        for model_name, result in results.items():
            if "error" in result:
                continue
                
            analysis["summary"][model_name] = {
                "speed_rank": 0,  # 後で計算
                "memory_rank": 0,  # 後で計算
                "loading_time": result["loading_time"],
                "docs_per_second": result["docs_per_second"],
                "memory_overhead": result["memory_usage"]["peak_overhead"]
            }
        
        # 順位付け
        valid_models = [k for k, v in results.items() if "error" not in v]
        
        # 速度順位
        speed_sorted = sorted(
            valid_models, 
            key=lambda x: results[x]["docs_per_second"], 
            reverse=True
        )
        for rank, model in enumerate(speed_sorted, 1):
            analysis["summary"][model]["speed_rank"] = rank
        
        # メモリ効率順位
        memory_sorted = sorted(
            valid_models,
            key=lambda x: results[x]["memory_usage"]["peak_overhead"]
        )
        for rank, model in enumerate(memory_sorted, 1):
            analysis["summary"][model]["memory_rank"] = rank
        
        # 推奨事項生成
        if valid_models:
            fastest_model = speed_sorted[0]
            most_memory_efficient = memory_sorted[0] 
            
            analysis["recommendations"] = {
                "fastest": {
                    "model": fastest_model,
                    "docs_per_second": results[fastest_model]["docs_per_second"],
                    "use_case": "高スループット要求時"
                },
                "most_memory_efficient": {
                    "model": most_memory_efficient,
                    "memory_overhead": results[most_memory_efficient]["memory_usage"]["peak_overhead"],
                    "use_case": "メモリ制約環境"
                },
                "balanced": {
                    "model": "ja_core_news_md",  # 通常は中間モデルが推奨
                    "reason": "精度とパフォーマンスのバランス"
                }
            }
        
        return analysis
```

## カスタムコンポーネント統合

### パイプラインカスタマイゼーション
```python
class CustomJapaneseNLPPipeline:
    """カスタム日本語NLPパイプライン"""
    
    def __init__(self, base_model: str = "ja_core_news_md"):
        import spacy
        from spacy.tokens import Span
        
        self.nlp = spacy.load(base_model)
        self._add_custom_components()
    
    def _add_custom_components(self):
        """カスタムコンポーネント追加"""
        
        # 日本固有の個人情報認識コンポーネント
        @self.nlp.Language.component("japanese_pii_detector")
        def japanese_pii_detector(doc):
            """日本語個人情報検出コンポーネント"""
            import re
            
            patterns = {
                "MY_NUMBER": r'\b\d{4}-\d{4}-\d{4}\b|\b\d{12}\b',
                "POSTAL_CODE": r'\b\d{3}-\d{4}\b|\b〒\s*\d{3}-?\d{4}\b',
                "PHONE_JP": r'\b0\d{1,4}-\d{2,4}-\d{4}\b|\b0\d{9,10}\b',
                "BANK_ACCOUNT": r'\b\d{7}\b',  # 銀行口座番号
                "CREDIT_CARD": r'\b\d{4}-\d{4}-\d{4}-\d{4}\b|\b\d{16}\b'
            }
            
            new_ents = []
            
            for label, pattern in patterns.items():
                matches = re.finditer(pattern, doc.text)
                for match in matches:
                    start_char = match.start()
                    end_char = match.end()
                    
                    # 文字位置をトークン位置に変換
                    start_token = None
                    end_token = None
                    
                    for token in doc:
                        if token.idx <= start_char < token.idx + len(token.text):
                            start_token = token.i
                        if token.idx < end_char <= token.idx + len(token.text):
                            end_token = token.i + 1
                            break
                    
                    if start_token is not None and end_token is not None:
                        span = Span(doc, start_token, end_token, label=label)
                        new_ents.append(span)
            
            # 既存のエンティティと結合（重複排除）
            existing_ents = list(doc.ents)
            all_ents = existing_ents + new_ents
            
            # 重複除去とソート
            unique_ents = []
            for ent in sorted(all_ents, key=lambda x: x.start):
                # 重複チェック
                overlap = False
                for existing in unique_ents:
                    if (ent.start < existing.end and ent.end > existing.start):
                        overlap = True
                        break
                
                if not overlap:
                    unique_ents.append(ent)
            
            doc.ents = unique_ents
            return doc
        
        # パイプライン追加
        if "japanese_pii_detector" not in self.nlp.pipe_names:
            self.nlp.add_pipe("japanese_pii_detector", after="ner")
        
        # 信頼度スコア調整コンポーネント  
        @self.nlp.Language.component("confidence_adjuster")
        def confidence_adjuster(doc):
            """エンティティ信頼度スコア調整"""
            
            adjusted_ents = []
            
            for ent in doc.ents:
                # 日本語固有パターンの信頼度向上
                confidence_boost = 0.0
                
                if ent.label_ in ["MY_NUMBER", "POSTAL_CODE", "PHONE_JP"]:
                    confidence_boost = 0.2
                elif ent.label_ == "PERSON" and self._is_japanese_name(ent.text):
                    confidence_boost = 0.1
                
                # スコアを属性として保存
                ent._.confidence_score = min(1.0, ent._.get("confidence_score", 0.8) + confidence_boost)
                adjusted_ents.append(ent)
            
            return doc
        
        # カスタム属性登録
        if not Span.has_extension("confidence_score"):
            Span.set_extension("confidence_score", default=0.8)
        
        if "confidence_adjuster" not in self.nlp.pipe_names:
            self.nlp.add_pipe("confidence_adjuster", last=True)
    
    def _is_japanese_name(self, text: str) -> bool:
        """日本人名判定"""
        import re
        
        # ひらがな、カタカナ、漢字のみで構成
        japanese_chars = re.compile(r'^[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]+$')
        
        # 2-4文字の長さ
        return (japanese_chars.match(text) and 2 <= len(text) <= 4)
    
    def process_text(self, text: str) -> Dict[str, Any]:
        """テキスト処理実行"""
        
        doc = self.nlp(text)
        
        entities = []
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "label": ent.label_,
                "confidence": ent._.confidence_score if ent._.has("confidence_score") else 0.8
            })
        
        return {
            "text": text,
            "entities": entities,
            "tokens": [{"text": token.text, "pos": token.pos_, "lemma": token.lemma_} for token in doc],
            "processing_info": {
                "model": self.nlp.meta["name"],
                "pipeline": self.nlp.pipe_names,
                "language": self.nlp.meta["lang"]
            }
        }
```

## 統合テストフレームワーク

### 自動化テストスイート
```python
import pytest
from typing import List, Dict, Any

class SpacyIntegrationTestSuite:
    """spaCy統合テストスイート"""
    
    @pytest.fixture(scope="session")
    def models_to_test(self):
        """テスト対象モデル一覧"""
        return ["ja_core_news_sm", "ja_core_news_md"]  # CI環境では軽量モデルのみ
    
    @pytest.fixture(scope="session")
    def test_cases(self):
        """テストケース定義"""
        return [
            {
                "id": "basic_person_detection",
                "text": "田中太郎さんが来訪しました。",
                "expected_entities": [
                    {"label": "PERSON", "text": "田中太郎", "min_confidence": 0.8}
                ]
            },
            {
                "id": "organization_detection", 
                "text": "株式会社テストで働いています。",
                "expected_entities": [
                    {"label": "ORG", "text": "株式会社テスト", "min_confidence": 0.7}
                ]
            },
            {
                "id": "mixed_entities",
                "text": "佐藤花子は東京都に住んでいて、03-1234-5678に電話できます。",
                "expected_entities": [
                    {"label": "PERSON", "text": "佐藤花子", "min_confidence": 0.8},
                    {"label": "GPE", "text": "東京都", "min_confidence": 0.7},
                    {"label": "PHONE_JP", "text": "03-1234-5678", "min_confidence": 0.9}
                ]
            }
        ]
    
    def test_model_loading(self, models_to_test):
        """モデル読み込みテスト"""
        import spacy
        
        for model_name in models_to_test:
            try:
                nlp = spacy.load(model_name)
                assert nlp is not None
                assert nlp.meta["name"] == model_name
                
                # 基本パイプライン確認
                expected_pipes = ["tok2vec", "tagger", "parser", "ner"]
                for pipe in expected_pipes:
                    assert pipe in nlp.pipe_names
                    
            except OSError as e:
                pytest.skip(f"Model {model_name} not installed: {e}")
    
    def test_basic_nlp_functionality(self, models_to_test):
        """基本NLP機能テスト"""
        import spacy
        
        test_text = "これはテストです。"
        
        for model_name in models_to_test:
            try:
                nlp = spacy.load(model_name)
                doc = nlp(test_text)
                
                # トークン化確認
                assert len(doc) > 0
                
                # 品詞タグ確認
                pos_tags = [token.pos_ for token in doc]
                assert all(tag for tag in pos_tags)  # 空でないタグ
                
                # 依存関係解析確認
                deps = [token.dep_ for token in doc]
                assert all(dep for dep in deps)  # 空でない依存関係
                
            except OSError:
                pytest.skip(f"Model {model_name} not available")
    
    def test_entity_recognition_accuracy(self, models_to_test, test_cases):
        """エンティティ認識精度テスト"""
        import spacy
        
        for model_name in models_to_test:
            try:
                nlp = spacy.load(model_name)
                
                for test_case in test_cases:
                    doc = nlp(test_case["text"])
                    detected_entities = [
                        {"label": ent.label_, "text": ent.text}
                        for ent in doc.ents
                    ]
                    
                    # 期待エンティティの存在確認
                    for expected in test_case["expected_entities"]:
                        found = any(
                            ent["label"] == expected["label"] and 
                            ent["text"] == expected["text"]
                            for ent in detected_entities
                        )
                        
                        assert found, f"Expected entity not found: {expected} in {detected_entities}"
                        
            except OSError:
                pytest.skip(f"Model {model_name} not available")
    
    def test_custom_pipeline_integration(self, models_to_test):
        """カスタムパイプライン統合テスト"""
        
        for model_name in models_to_test:
            try:
                pipeline = CustomJapaneseNLPPipeline(model_name)
                
                # カスタムコンポーネント確認
                assert "japanese_pii_detector" in pipeline.nlp.pipe_names
                assert "confidence_adjuster" in pipeline.nlp.pipe_names
                
                # 日本語固有PII検出テスト
                test_text = "マイナンバー: 1234-5678-9012, 郵便番号: 123-4567"
                result = pipeline.process_text(test_text)
                
                # カスタムエンティティ検出確認
                my_number_found = any(
                    ent["label"] == "MY_NUMBER" for ent in result["entities"]
                )
                postal_found = any(
                    ent["label"] == "POSTAL_CODE" for ent in result["entities"]
                )
                
                assert my_number_found, "MY_NUMBER entity not detected"
                assert postal_found, "POSTAL_CODE entity not detected"
                
            except OSError:
                pytest.skip(f"Model {model_name} not available")
    
    def test_performance_requirements(self, models_to_test):
        """パフォーマンス要件テスト"""
        import time
        import spacy
        
        test_text = "田中太郎さんは東京都に住んでいます。" * 10  # ある程度の長さ
        
        for model_name in models_to_test:
            try:
                nlp = spacy.load(model_name)
                
                # 処理時間測定
                start_time = time.time()
                doc = nlp(test_text)
                processing_time = time.time() - start_time
                
                # パフォーマンス要件確認（モデルによって基準を変える）
                time_thresholds = {
                    "ja_core_news_sm": 0.1,   # 100ms以内
                    "ja_core_news_md": 0.2,   # 200ms以内
                    "ja_core_news_lg": 0.5,   # 500ms以内
                    "ja_core_news_trf": 1.0   # 1秒以内
                }
                
                threshold = time_thresholds.get(model_name, 0.5)
                assert processing_time < threshold, f"Processing time {processing_time:.3f}s exceeds threshold {threshold}s"
                
            except OSError:
                pytest.skip(f"Model {model_name} not available")

# テスト実行用コマンド
"""
# 全テスト実行
pytest tests/test_spacy_integration.py -v

# 特定テスト実行
pytest tests/test_spacy_integration.py::SpacyIntegrationTestSuite::test_model_loading -v

# カバレッジ付きテスト
pytest tests/test_spacy_integration.py --cov=src/nlp --cov-report=html

# 並列テスト実行
pytest tests/test_spacy_integration.py -n auto
"""
```

## モデル最適化・チューニング

### パフォーマンスチューニング設定
```python
class SpacyOptimizer:
    """spaCy最適化設定クラス"""
    
    def __init__(self, model_name: str):
        import spacy
        self.model_name = model_name
        self.nlp = spacy.load(model_name)
    
    def optimize_for_production(self) -> spacy.Language:
        """本番環境用最適化"""
        
        # 不要なパイプラインコンポーネント除去
        unnecessary_pipes = ["tagger", "parser"]  # NERのみ必要な場合
        
        for pipe_name in unnecessary_pipes:
            if pipe_name in self.nlp.pipe_names:
                self.nlp.remove_pipe(pipe_name)
                print(f"Removed unnecessary pipe: {pipe_name}")
        
        # バッチサイズ最適化
        self.nlp.max_length = 1000000  # 大きなドキュメント対応
        
        # GPU使用（利用可能な場合）
        if spacy.prefer_gpu():
            print("GPU acceleration enabled")
        
        return self.nlp
    
    def optimize_for_batch_processing(self, batch_size: int = 32) -> spacy.Language:
        """バッチ処理用最適化"""
        
        # バッチ処理設定
        self.nlp.batch_size = batch_size
        
        # 並列処理設定
        import multiprocessing
        n_cores = multiprocessing.cpu_count()
        self.nlp.n_process = min(4, n_cores)  # 最大4プロセス
        
        return self.nlp
    
    def create_lightweight_pipeline(self) -> spacy.Language:
        """軽量パイプライン作成"""
        import spacy
        
        # 最小構成パイプライン作成
        nlp = spacy.blank("ja")
        
        # 必要最小限のコンポーネントのみ追加
        nlp.add_pipe("sentencizer")  # 文分割
        
        # カスタム軽量NER追加
        from spacy.pipeline import EntityRuler
        
        ruler = nlp.add_pipe("entity_ruler")
        
        # 高精度パターンのみ定義
        patterns = [
            {"label": "MY_NUMBER", "pattern": [{"TEXT": {"REGEX": r"\d{4}-\d{4}-\d{4}"}}]},
            {"label": "PHONE_JP", "pattern": [{"TEXT": {"REGEX": r"0\d{1,4}-\d{2,4}-\d{4}"}}]},
            {"label": "POSTAL_CODE", "pattern": [{"TEXT": {"REGEX": r"\d{3}-\d{4}"}}]},
        ]
        
        ruler.add_patterns(patterns)
        
        return nlp
```

このspaCy統合・テスト戦略により、PresidioPDFプロジェクトにおける日本語自然言語処理の品質と性能を保証し、効率的な開発・運用を支援します。