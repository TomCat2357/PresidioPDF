# Microsoft Presidio 統合ガイド

## 概要
Microsoft Presidio を PresidioPDF プロジェクトに統合するための詳細ガイド。日本語個人情報検出に特化した設定と実装パターンを提供し、高精度な PII 検出を実現する。

## Presidio アーキテクチャ理解

### コンポーネント構成
```python
# Presidio 主要コンポーネント
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# アーキテクチャ概要
"""
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Analyzer       │───▶│  NLP Engine     │───▶│  Recognizers    │
│  Engine         │    │  (spaCy/Stanza) │    │  (Built-in +    │
│                 │    │                 │    │   Custom)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐    ┌─────────────────┐
│  Anonymizer     │───▶│  Operators      │
│  Engine         │    │  (Mask/Replace/ │
│                 │    │   Encrypt/etc.) │
└─────────────────┘    └─────────────────┘
"""
```

## 日本語 NLP エンジン設定

### spaCy 統合設定
```python
# NLP エンジン設定
class JapaneseNLPConfig:
    """日本語 NLP エンジン設定クラス"""
    
    def __init__(self, model_name: str = "ja_core_news_sm"):
        self.model_name = model_name
        self.supported_languages = ["ja"]
        
    def create_nlp_engine(self) -> NlpEngineProvider:
        """日本語対応 NLP エンジン作成"""
        
        # spaCy 設定
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [
                {
                    "lang_code": "ja", 
                    "model_name": self.model_name
                }
            ]
        }
        
        nlp_engine = NlpEngineProvider(nlp_configuration=configuration)
        return nlp_engine.create_engine()

# Analyzer Engine 初期化
class PresidioAnalyzerSetup:
    """Presidio Analyzer セットアップ"""
    
    def __init__(self, spacy_model: str = "ja_core_news_sm"):
        self.spacy_model = spacy_model
        self.analyzer = None
        self.anonymizer = None
        
    def setup_analyzer(self) -> AnalyzerEngine:
        """Analyzer Engine セットアップ"""
        
        # NLP エンジン設定
        nlp_config = JapaneseNLPConfig(self.spacy_model)
        nlp_engine = nlp_config.create_nlp_engine()
        
        # Analyzer 初期化
        analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            supported_languages=["ja"],
            default_score_threshold=0.7
        )
        
        # カスタム日本語認識器追加
        self._add_japanese_recognizers(analyzer)
        
        self.analyzer = analyzer
        return analyzer
    
    def setup_anonymizer(self) -> AnonymizerEngine:
        """Anonymizer Engine セットアップ"""
        self.anonymizer = AnonymizerEngine()
        return self.anonymizer
    
    def _add_japanese_recognizers(self, analyzer: AnalyzerEngine):
        """日本語カスタム認識器追加"""
        
        # 日本の電話番号認識器
        jp_phone_recognizer = self._create_japanese_phone_recognizer()
        analyzer.registry.add_recognizer(jp_phone_recognizer)
        
        # 日本の郵便番号認識器
        jp_postal_recognizer = self._create_japanese_postal_recognizer()
        analyzer.registry.add_recognizer(jp_postal_recognizer)
        
        # マイナンバー認識器
        my_number_recognizer = self._create_my_number_recognizer()
        analyzer.registry.add_recognizer(my_number_recognizer)
        
        # 日本の住所認識器
        jp_address_recognizer = self._create_japanese_address_recognizer()
        analyzer.registry.add_recognizer(jp_address_recognizer)
```

## 日本語カスタム認識器実装

### 電話番号認識器
```python
def _create_japanese_phone_recognizer(self) -> PatternRecognizer:
    """日本の電話番号パターン認識器"""
    
    # 日本の電話番号パターン
    jp_phone_patterns = [
        # 固定電話: 0X-XXXX-XXXX, 0XX-XXX-XXXX, 0XXX-XX-XXXX
        r'\b0\d{1,4}-\d{2,4}-\d{4}\b',
        
        # 携帯電話: 0X0-XXXX-XXXX
        r'\b0[789]0-\d{4}-\d{4}\b',
        
        # ハイフンなし形式
        r'\b0\d{9,10}\b',
        
        # 括弧形式: (0XX) XXX-XXXX
        r'\(\d{2,4}\)\s*\d{2,4}-\d{4}',
        
        # 国際形式: +81-X-XXXX-XXXX
        r'\+81-\d{1,4}-\d{2,4}-\d{4}',
    ]
    
    return PatternRecognizer(
        supported_entity="JP_PHONE_NUMBER",
        patterns=[{"name": "jp_phone", "regex": pattern, "score": 0.9}
                 for pattern in jp_phone_patterns],
        context=["電話", "TEL", "連絡先", "番号", "phone", "tel"]
    )

def _create_japanese_postal_recognizer(self) -> PatternRecognizer:
    """日本の郵便番号認識器"""
    
    postal_patterns = [
        # 標準形式: XXX-XXXX
        r'\b\d{3}-\d{4}\b',
        
        # ハイフンなし: XXXXXXX
        r'\b\d{7}\b',
        
        # 〒マーク付き
        r'〒\s*\d{3}-?\d{4}',
    ]
    
    return PatternRecognizer(
        supported_entity="JP_POSTAL_CODE",
        patterns=[{"name": "jp_postal", "regex": pattern, "score": 0.95}
                 for pattern in postal_patterns],
        context=["郵便", "住所", "〒", "postal", "zip"]
    )

def _create_my_number_recognizer(self) -> PatternRecognizer:
    """マイナンバー認識器"""
    
    # マイナンバーは12桁
    my_number_patterns = [
        # ハイフンあり: XXXX-XXXX-XXXX
        r'\b\d{4}-\d{4}-\d{4}\b',
        
        # スペースあり: XXXX XXXX XXXX
        r'\b\d{4}\s+\d{4}\s+\d{4}\b',
        
        # 連続12桁
        r'\b\d{12}\b',
    ]
    
    return PatternRecognizer(
        supported_entity="MY_NUMBER",
        patterns=[{"name": "my_number", "regex": pattern, "score": 0.99}
                 for pattern in my_number_patterns],
        context=["マイナンバー", "個人番号", "mynumber", "個人識別符号"]
    )

def _create_japanese_address_recognizer(self) -> PatternRecognizer:
    """日本の住所認識器"""
    
    # 都道府県リスト
    prefectures = [
        "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
        "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
        "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
        "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
        "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
        "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
        "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
    ]
    
    prefecture_pattern = "|".join(prefectures)
    
    address_patterns = [
        # 完全住所パターン
        rf'({prefecture_pattern})[^。\n]+?[市区町村][^。\n]+?[丁目町番地号][\d\-]+',
        
        # 簡略住所パターン
        rf'({prefecture_pattern})[^。\n]+?[市区町村]',
        
        # 番地パターン
        r'[0-9０-９]+[-ー][0-9０-９]+[-ー][0-9０-９]+',
    ]
    
    return PatternRecognizer(
        supported_entity="JP_ADDRESS",
        patterns=[{"name": "jp_address", "regex": pattern, "score": 0.85}
                 for pattern in address_patterns],
        context=["住所", "所在地", "address", "location", "居住地"]
    )
```

## 高度な検出設定

### コンテキスト認識の強化
```python
class ContextAwareRecognizer:
    """コンテキスト認識強化クラス"""
    
    def __init__(self, analyzer: AnalyzerEngine):
        self.analyzer = analyzer
        
    def analyze_with_context(
        self, 
        text: str, 
        context_clues: List[str] = None
    ) -> List[RecognizerResult]:
        """コンテキスト情報を活用した分析"""
        
        # 基本分析実行
        results = self.analyzer.analyze(
            text=text, 
            language='ja',
            entities=["PERSON", "JP_PHONE_NUMBER", "JP_POSTAL_CODE", 
                     "MY_NUMBER", "JP_ADDRESS", "EMAIL_ADDRESS"]
        )
        
        # コンテキストベーススコア調整
        if context_clues:
            results = self._adjust_scores_by_context(results, text, context_clues)
        
        return results
    
    def _adjust_scores_by_context(
        self, 
        results: List[RecognizerResult], 
        text: str, 
        context_clues: List[str]
    ) -> List[RecognizerResult]:
        """コンテキスト情報によるスコア調整"""
        
        adjusted_results = []
        
        for result in results:
            # テキスト周辺のコンテキスト取得
            start_context = max(0, result.start - 50)
            end_context = min(len(text), result.end + 50)
            surrounding_text = text[start_context:end_context].lower()
            
            # コンテキストマッチング
            context_boost = 0.0
            for clue in context_clues:
                if clue.lower() in surrounding_text:
                    context_boost += 0.1
            
            # スコア調整
            new_score = min(1.0, result.score + context_boost)
            
            adjusted_result = RecognizerResult(
                entity_type=result.entity_type,
                start=result.start,
                end=result.end,
                score=new_score
            )
            
            adjusted_results.append(adjusted_result)
        
        return adjusted_results

# 使用例
context_analyzer = ContextAwareRecognizer(analyzer)
results = context_analyzer.analyze_with_context(
    text="田中太郎の連絡先は03-1234-5678です。",
    context_clues=["連絡先", "電話", "名前"]
)
```

### カスタムエンティティ学習
```python
class CustomEntityTrainer:
    """カスタムエンティティ学習クラス"""
    
    def __init__(self):
        self.training_data = []
        
    def add_training_sample(
        self, 
        text: str, 
        entities: List[Tuple[int, int, str]]
    ):
        """学習サンプル追加"""
        self.training_data.append({
            "text": text,
            "entities": entities
        })
    
    def create_pattern_recognizer(
        self, 
        entity_type: str, 
        min_confidence: float = 0.8
    ) -> PatternRecognizer:
        """パターン認識器生成"""
        
        # 学習データからパターン抽出
        patterns = self._extract_patterns(entity_type)
        
        return PatternRecognizer(
            supported_entity=entity_type,
            patterns=[{"name": f"{entity_type.lower()}_pattern", 
                      "regex": pattern, 
                      "score": min_confidence}
                     for pattern in patterns]
        )
    
    def _extract_patterns(self, entity_type: str) -> List[str]:
        """エンティティタイプからパターン抽出"""
        patterns = set()
        
        for sample in self.training_data:
            text = sample["text"]
            for start, end, label in sample["entities"]:
                if label == entity_type:
                    entity_text = text[start:end]
                    # 簡易パターン生成
                    pattern = self._generalize_pattern(entity_text)
                    patterns.add(pattern)
        
        return list(patterns)
    
    def _generalize_pattern(self, text: str) -> str:
        """テキストからパターン汎化"""
        import re
        
        # 数字を \d+ に置換
        pattern = re.sub(r'\d+', r'\\d+', text)
        
        # 英文字を適切なパターンに置換
        pattern = re.sub(r'[a-zA-Z]+', r'[a-zA-Z]+', pattern)
        
        # 特殊文字をエスケープ
        pattern = re.escape(pattern).replace(r'\\\d\+', r'\d+').replace(r'\\\[a-zA-Z\]\+', r'[a-zA-Z]+')
        
        return f'\\b{pattern}\\b'

# 使用例
trainer = CustomEntityTrainer()

# 学習データ追加
trainer.add_training_sample(
    "社員番号：EMP12345",
    [(5, 12, "EMPLOYEE_ID")]
)

trainer.add_training_sample(
    "職員ID: STF99999", 
    [(4, 12, "EMPLOYEE_ID")]
)

# カスタム認識器作成
employee_recognizer = trainer.create_pattern_recognizer("EMPLOYEE_ID", 0.9)
```

## 匿名化・マスキング設定

### 高度な匿名化オペレーター
```python
from presidio_anonymizer.entities import OperatorConfig

class JapaneseAnonymizer:
    """日本語対応匿名化エンジン"""
    
    def __init__(self):
        self.anonymizer = AnonymizerEngine()
        
    def anonymize_japanese_text(
        self, 
        text: str, 
        analyzer_results: List[RecognizerResult],
        anonymization_config: Dict[str, str] = None
    ) -> str:
        """日本語テキスト匿名化"""
        
        # デフォルト設定
        default_config = {
            "PERSON": "mask",
            "JP_PHONE_NUMBER": "mask", 
            "JP_POSTAL_CODE": "mask",
            "MY_NUMBER": "mask",
            "JP_ADDRESS": "replace",
            "EMAIL_ADDRESS": "hash"
        }
        
        config = anonymization_config or default_config
        
        # オペレーター設定作成
        operators = {}
        for entity_type, operation in config.items():
            operators[entity_type] = self._create_operator_config(operation)
        
        # 匿名化実行
        result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=analyzer_results,
            operators=operators
        )
        
        return result.text
    
    def _create_operator_config(self, operation: str) -> OperatorConfig:
        """操作タイプ別設定作成"""
        
        if operation == "mask":
            return OperatorConfig("mask", {"chars_to_mask": 5, "masking_char": "■"})
        
        elif operation == "replace":
            return OperatorConfig("replace", {"new_value": "[匿名化済み]"})
        
        elif operation == "hash":
            return OperatorConfig("hash", {"hash_type": "sha256"})
        
        elif operation == "encrypt":
            return OperatorConfig("encrypt", {"key": "mySecretKey"})
        
        else:
            return OperatorConfig("redact", {})

# カスタムマスキングパターン
class CustomMaskOperator:
    """カスタムマスキングオペレーター"""
    
    @staticmethod
    def japanese_name_mask(text: str) -> str:
        """日本人名のマスキング"""
        # 姓は完全マスク、名は最初の1文字残す
        if len(text) <= 2:
            return "■" * len(text)
        elif len(text) == 3:
            return "■■" + text[2]
        else:
            return "■■" + text[2] + "■" * (len(text) - 3)
    
    @staticmethod
    def phone_number_mask(text: str) -> str:
        """電話番号の部分マスキング"""
        import re
        # 最初の3桁と最後の4桁を残す
        if re.match(r'\d{3}-\d{4}-\d{4}', text):
            parts = text.split('-')
            return f"{parts[0]}-■■■■-{parts[2]}"
        return "■■■-■■■■-■■■■"
    
    @staticmethod 
    def address_mask(text: str) -> str:
        """住所の階層的マスキング"""
        # 都道府県のみ残し、それ以下をマスク
        prefectures = ["東京都", "大阪府", "京都府", "北海道"]
        
        for pref in prefectures:
            if text.startswith(pref):
                return pref + "■■■■■"
        
        # その他の県
        if text.endswith("県"):
            pref_end = text.find("県") + 1
            return text[:pref_end] + "■■■■■"
            
        return "■■■■■"
```

## パフォーマンス最適化

### バッチ処理最適化
```python
class OptimizedPresidioProcessor:
    """最適化Presidio処理クラス"""
    
    def __init__(self, spacy_model: str = "ja_core_news_sm"):
        self.analyzer = None
        self.anonymizer = None
        self.batch_size = 32
        self.setup_engines(spacy_model)
    
    def setup_engines(self, spacy_model: str):
        """エンジン初期化"""
        setup = PresidioAnalyzerSetup(spacy_model)
        self.analyzer = setup.setup_analyzer()
        self.anonymizer = setup.setup_anonymizer()
    
    def process_texts_batch(
        self, 
        texts: List[str], 
        anonymize: bool = True
    ) -> List[Dict[str, Any]]:
        """テキストのバッチ処理"""
        
        results = []
        
        # バッチ単位で処理
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_results = self._process_batch(batch, anonymize)
            results.extend(batch_results)
        
        return results
    
    def _process_batch(
        self, 
        batch: List[str], 
        anonymize: bool
    ) -> List[Dict[str, Any]]:
        """バッチ単位処理"""
        
        batch_results = []
        
        # 並列処理で分析
        from concurrent.futures import ThreadPoolExecutor
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            analysis_futures = [
                executor.submit(self.analyzer.analyze, text, 'ja')
                for text in batch
            ]
            
            for i, future in enumerate(analysis_futures):
                try:
                    analyzer_results = future.result()
                    
                    result = {
                        "original_text": batch[i],
                        "analyzer_results": analyzer_results,
                        "anonymized_text": None,
                        "processing_time": None
                    }
                    
                    # 匿名化実行
                    if anonymize and analyzer_results:
                        start_time = time.time()
                        anonymizer_result = self.anonymizer.anonymize(
                            text=batch[i],
                            analyzer_results=analyzer_results
                        )
                        result["anonymized_text"] = anonymizer_result.text
                        result["processing_time"] = time.time() - start_time
                    
                    batch_results.append(result)
                    
                except Exception as e:
                    # エラーハンドリング
                    batch_results.append({
                        "original_text": batch[i],
                        "error": str(e),
                        "analyzer_results": [],
                        "anonymized_text": None,
                        "processing_time": None
                    })
        
        return batch_results

# メモリ効率的な処理
class MemoryEfficientProcessor:
    """メモリ効率的処理クラス"""
    
    def __init__(self, analyzer: AnalyzerEngine, anonymizer: AnonymizerEngine):
        self.analyzer = analyzer
        self.anonymizer = anonymizer
    
    def process_large_text(
        self, 
        text: str, 
        chunk_size: int = 1000
    ) -> str:
        """大容量テキストの分割処理"""
        
        if len(text) <= chunk_size:
            return self._process_single_chunk(text)
        
        # テキスト分割
        chunks = self._split_text_intelligently(text, chunk_size)
        
        # 各チャンク処理
        processed_chunks = []
        for chunk in chunks:
            processed_chunk = self._process_single_chunk(chunk)
            processed_chunks.append(processed_chunk)
        
        return ''.join(processed_chunks)
    
    def _split_text_intelligently(self, text: str, chunk_size: int) -> List[str]:
        """文境界を考慮した分割"""
        import re
        
        chunks = []
        current_pos = 0
        
        # 文区切り文字での分割
        sentence_endings = re.finditer(r'[。！？\n]', text)
        
        last_end = 0
        current_chunk = ""
        
        for match in sentence_endings:
            sentence = text[last_end:match.end()]
            
            if len(current_chunk + sentence) <= chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
            
            last_end = match.end()
        
        # 残りのテキスト
        if last_end < len(text):
            remaining = text[last_end:]
            if current_chunk:
                if len(current_chunk + remaining) <= chunk_size:
                    current_chunk += remaining
                    chunks.append(current_chunk)
                else:
                    chunks.append(current_chunk)
                    chunks.append(remaining)
            else:
                chunks.append(remaining)
        elif current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _process_single_chunk(self, chunk: str) -> str:
        """単一チャンク処理"""
        try:
            # 分析実行
            results = self.analyzer.analyze(chunk, 'ja')
            
            # 匿名化実行
            if results:
                anonymized = self.anonymizer.anonymize(
                    text=chunk,
                    analyzer_results=results
                )
                return anonymized.text
            else:
                return chunk
                
        except Exception as e:
            logging.error(f"Chunk processing error: {e}")
            return chunk
```

## テスト・デバッグ支援

### 検出精度評価
```python
class PresidioEvaluator:
    """Presidio検出精度評価クラス"""
    
    def __init__(self, analyzer: AnalyzerEngine):
        self.analyzer = analyzer
        
    def evaluate_precision_recall(
        self, 
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """適合率・再現率評価"""
        
        true_positives = 0
        false_positives = 0
        false_negatives = 0
        
        for case in test_cases:
            text = case["text"]
            expected_entities = set(case["expected_entities"])
            
            # Presidio分析実行
            results = self.analyzer.analyze(text, 'ja')
            detected_entities = set()
            
            for result in results:
                entity_span = (result.start, result.end, result.entity_type)
                detected_entities.add(entity_span)
            
            # 評価計算
            tp = len(expected_entities & detected_entities)
            fp = len(detected_entities - expected_entities)
            fn = len(expected_entities - detected_entities)
            
            true_positives += tp
            false_positives += fp
            false_negatives += fn
        
        # 指標計算
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives
        }

# テストケース例
test_cases = [
    {
        "text": "私の名前は田中太郎で、電話番号は03-1234-5678です。",
        "expected_entities": [
            (5, 9, "PERSON"),      # 田中太郎
            (18, 30, "JP_PHONE_NUMBER")  # 03-1234-5678
        ]
    }
]

evaluator = PresidioEvaluator(analyzer)
metrics = evaluator.evaluate_precision_recall(test_cases)
print(f"Precision: {metrics['precision']:.3f}")
print(f"Recall: {metrics['recall']:.3f}")
print(f"F1 Score: {metrics['f1_score']:.3f}")
```

この統合ガイドにより、Microsoft Presidio を PresidioPDF プロジェクトに効果的に組み込み、高精度な日本語個人情報検出・匿名化システムを構築できます。