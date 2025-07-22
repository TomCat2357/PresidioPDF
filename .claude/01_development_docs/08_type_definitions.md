# 型定義

## 概要
PresidioPDFプロジェクト全体で使用する型定義を統一管理する。Python型ヒント（typing）、Pydantic、mypy strict modeに完全対応し、型安全性を最大限に確保する。

## 基本型定義

### プリミティブ型エイリアス
```python
from typing import Union, Optional, List, Dict, Any, Tuple, Callable
from typing_extensions import Literal, TypedDict, Protocol
from pathlib import Path
from datetime import datetime
from uuid import UUID

# 基本型エイリアス
EntityType = Literal["PERSON", "LOCATION", "PHONE_NUMBER", "EMAIL_ADDRESS", 
                     "CREDIT_CARD", "DATE_TIME", "ORGANIZATION", "CUSTOM"]
ConfidenceScore = float  # 0.0 - 1.0
PageNumber = int  # 1-based
ProcessingStatus = Literal["pending", "processing", "completed", "error", "cancelled"]
MaskingMethod = Literal["annotation", "highlight", "both"]
SpaCyModel = Literal["ja_core_news_sm", "ja_core_news_md", "ja_core_news_lg", "ja_core_news_trf"]
```

## コア業務オブジェクト型

### 検出エンティティ
```python
from pydantic import BaseModel, Field, validator
from typing import Optional

class Coordinates(BaseModel):
    """PDF内の座標情報"""
    x: float = Field(..., ge=0, description="X座標")
    y: float = Field(..., ge=0, description="Y座標") 
    width: float = Field(..., gt=0, description="幅")
    height: float = Field(..., gt=0, description="高さ")
    
    class Config:
        schema_extra = {
            "example": {"x": 150.5, "y": 200.3, "width": 60.2, "height": 15.8}
        }

class EntityDetection(BaseModel):
    """個人情報検出結果"""
    entity_type: EntityType = Field(..., description="エンティティ種別")
    text: str = Field(..., min_length=1, description="検出されたテキスト")
    start: int = Field(..., ge=0, description="開始位置（文字単位）")
    end: int = Field(..., gt=0, description="終了位置（文字単位）")
    confidence: ConfidenceScore = Field(..., ge=0, le=1, description="信頼度スコア")
    page: PageNumber = Field(..., ge=1, description="ページ番号")
    coordinates: Coordinates = Field(..., description="PDF内座標")
    
    @validator('end')
    def validate_end_after_start(cls, v, values):
        if 'start' in values and v <= values['start']:
            raise ValueError('end must be greater than start')
        return v
    
    @validator('text')
    def validate_text_length(cls, v, values):
        if 'start' in values and 'end' in values:
            expected_length = values['end'] - values['start']
            if len(v) != expected_length:
                raise ValueError(f'text length {len(v)} does not match position range {expected_length}')
        return v

class EntityStatistics(BaseModel):
    """検出統計情報"""
    total_count: int = Field(..., ge=0)
    by_type: Dict[EntityType, int] = Field(default_factory=dict)
    by_page: Dict[PageNumber, int] = Field(default_factory=dict)
    confidence_distribution: Dict[str, int] = Field(default_factory=dict)  # "high", "medium", "low"
```

### 処理設定
```python
class NLPConfig(BaseModel):
    """自然言語処理設定"""
    spacy_model: SpaCyModel = Field(default="ja_core_news_sm", description="使用するspaCyモデル")
    custom_entities: List[str] = Field(default_factory=list, description="カスタムエンティティ名")
    confidence_threshold: ConfidenceScore = Field(default=0.8, ge=0, le=1, description="検出閾値")
    batch_size: int = Field(default=32, ge=1, le=128, description="バッチサイズ")
    
    @validator('custom_entities')
    def validate_custom_entities(cls, v):
        # カスタムエンティティ名の検証
        for entity in v:
            if not entity.replace('_', '').isalnum():
                raise ValueError(f'Invalid custom entity name: {entity}')
        return v

class PDFProcessingConfig(BaseModel):
    """PDF処理設定"""
    masking_method: MaskingMethod = Field(default="annotation", description="マスキング方法")
    preserve_original: bool = Field(default=True, description="元ファイル保持")
    output_format: Literal["pdf", "json", "both"] = Field(default="pdf", description="出力形式")
    backup_enabled: bool = Field(default=True, description="バックアップ有効")
    
class EntityFilterConfig(BaseModel):
    """エンティティフィルタ設定"""
    enabled_entities: Dict[EntityType, bool] = Field(
        default_factory=lambda: {
            "PERSON": True,
            "LOCATION": True,
            "PHONE_NUMBER": True,
            "EMAIL_ADDRESS": True,
            "CREDIT_CARD": False,
            "DATE_TIME": False,
            "ORGANIZATION": False
        },
        description="有効なエンティティ種別"
    )
    min_confidence: ConfidenceScore = Field(default=0.7, ge=0, le=1)
    custom_patterns: Dict[str, str] = Field(default_factory=dict, description="カスタム正規表現パターン")

class ProcessingConfig(BaseModel):
    """総合処理設定"""
    nlp: NLPConfig = Field(default_factory=NLPConfig)
    pdf_processing: PDFProcessingConfig = Field(default_factory=PDFProcessingConfig)
    entity_filter: EntityFilterConfig = Field(default_factory=EntityFilterConfig)
    
    class Config:
        schema_extra = {
            "example": {
                "nlp": {
                    "spacy_model": "ja_core_news_sm",
                    "confidence_threshold": 0.8
                },
                "pdf_processing": {
                    "masking_method": "annotation",
                    "preserve_original": True
                },
                "entity_filter": {
                    "enabled_entities": {
                        "PERSON": True,
                        "LOCATION": True,
                        "PHONE_NUMBER": True
                    }
                }
            }
        }
```

### 処理結果
```python
from uuid import uuid4

class ProcessingResult(BaseModel):
    """処理結果"""
    processing_id: str = Field(default_factory=lambda: str(uuid4()), description="処理ID")
    status: ProcessingStatus = Field(..., description="処理ステータス")
    input_file: Path = Field(..., description="入力ファイルパス")
    output_file: Optional[Path] = Field(None, description="出力ファイルパス")
    detected_entities: List[EntityDetection] = Field(default_factory=list)
    statistics: EntityStatistics = Field(default_factory=EntityStatistics)
    config_snapshot: ProcessingConfig = Field(..., description="処理時設定スナップショット")
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = Field(None)
    error_message: Optional[str] = Field(None)
    
    @property
    def processing_duration(self) -> Optional[float]:
        """処理時間（秒）"""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def success(self) -> bool:
        """処理成功判定"""
        return self.status == "completed" and self.error_message is None
```

## サービス層プロトコル定義

### インターフェース型定義
```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Iterator

class PDFAnalyzer(Protocol):
    """PDF解析インターフェース"""
    
    def analyze_text(
        self, 
        text: str, 
        page_number: PageNumber = 1
    ) -> List[EntityDetection]:
        """テキスト解析"""
        ...
    
    def analyze_pdf(
        self,
        pdf_path: Path,
        config: NLPConfig
    ) -> List[EntityDetection]:
        """PDF全体解析"""
        ...

class PDFMasker(Protocol):
    """PDFマスキングインターフェース"""
    
    def apply_masking(
        self,
        pdf_path: Path,
        detections: List[EntityDetection],
        method: MaskingMethod = "annotation"
    ) -> Path:
        """マスキング適用"""
        ...
    
    def restore_from_backup(
        self,
        processing_id: str
    ) -> Path:
        """バックアップから復元"""
        ...

class ConfigManager(Protocol):
    """設定管理インターフェース"""
    
    def load_config(self, config_path: Optional[Path] = None) -> ProcessingConfig:
        """設定読み込み"""
        ...
    
    def save_config(self, config: ProcessingConfig, config_path: Path) -> None:
        """設定保存"""
        ...
    
    def validate_config(self, config: ProcessingConfig) -> bool:
        """設定検証"""
        ...
```

## Web UI用型定義

### APIリクエスト・レスポンス型
```python
class FileUploadRequest(BaseModel):
    """ファイルアップロード要求"""
    filename: str = Field(..., min_length=1)
    file_size: int = Field(..., gt=0, le=50*1024*1024)  # 50MB制限
    content_type: str = Field(..., regex=r"application/pdf")

class FileUploadResponse(BaseModel):
    """ファイルアップロード応答"""
    upload_id: str = Field(..., description="アップロードID")
    filename: str = Field(..., description="ファイル名")
    size: int = Field(..., description="ファイルサイズ（バイト）")
    upload_time: datetime = Field(default_factory=datetime.utcnow)

class ProcessingRequest(BaseModel):
    """処理開始要求"""
    upload_id: str = Field(..., description="アップロードID")
    config: Optional[ProcessingConfig] = Field(None, description="処理設定")
    
class ProcessingStatusResponse(BaseModel):
    """処理状況応答"""
    processing_id: str = Field(..., description="処理ID")
    status: ProcessingStatus = Field(..., description="ステータス")
    progress: float = Field(..., ge=0, le=100, description="進捗率（%）")
    message: Optional[str] = Field(None, description="状況メッセージ")
    current_page: Optional[PageNumber] = Field(None, description="処理中ページ")
    total_pages: Optional[int] = Field(None, ge=1, description="総ページ数")
    detected_count: int = Field(default=0, ge=0, description="検出済みエンティティ数")

class ProcessingResultResponse(BaseModel):
    """処理結果応答"""
    result: ProcessingResult = Field(..., description="処理結果")
    download_urls: Dict[str, str] = Field(
        default_factory=dict,
        description="ダウンロードURL（pdf, json, original）"
    )
```

### Web セッション型定義
```python
class UploadSession(TypedDict):
    upload_id: str
    filename: str
    file_path: Path
    upload_time: datetime
    expires_at: datetime

class ProcessingSession(TypedDict):
    processing_id: str
    upload_id: str
    status: ProcessingStatus
    start_time: datetime
    config: ProcessingConfig
    result: Optional[ProcessingResult]
```

## イベント・コールバック型定義

### 進捗コールバック
```python
ProgressCallback = Callable[[float, Optional[str]], None]
"""進捗コールバック型: (進捗率, メッセージ)"""

EntityCallback = Callable[[EntityDetection], None]
"""エンティティ検出コールバック型"""

class ProcessingCallbacks(BaseModel):
    """処理コールバック設定"""
    on_progress: Optional[ProgressCallback] = Field(None, description="進捗コールバック")
    on_entity_detected: Optional[EntityCallback] = Field(None, description="エンティティ検出コールバック")
    on_page_complete: Optional[Callable[[PageNumber], None]] = Field(None, description="ページ完了コールバック")
    on_error: Optional[Callable[[Exception], None]] = Field(None, description="エラーコールバック")
    
    class Config:
        arbitrary_types_allowed = True
```

## ファイル操作型定義

### ファイルハンドリング
```python
class FileInfo(BaseModel):
    """ファイル情報"""
    path: Path = Field(..., description="ファイルパス")
    size: int = Field(..., ge=0, description="ファイルサイズ")
    mime_type: str = Field(..., description="MIMEタイプ")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: Optional[datetime] = Field(None)
    
    @validator('path')
    def validate_path_exists(cls, v):
        if not v.exists():
            raise ValueError(f'File does not exist: {v}')
        return v
    
    @validator('mime_type')
    def validate_pdf_mime_type(cls, v):
        if v != 'application/pdf':
            raise ValueError(f'Invalid MIME type for PDF: {v}')
        return v

class BackupInfo(BaseModel):
    """バックアップ情報"""
    processing_id: str = Field(..., description="処理ID")
    original_file: Path = Field(..., description="元ファイルパス")
    backup_file: Path = Field(..., description="バックアップファイルパス")
    config_snapshot: ProcessingConfig = Field(..., description="設定スナップショット")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
class OutputFiles(BaseModel):
    """出力ファイル情報"""
    masked_pdf: Optional[Path] = Field(None, description="マスク済みPDF")
    report_json: Optional[Path] = Field(None, description="レポートJSON")
    backup_original: Optional[Path] = Field(None, description="元ファイルバックアップ")
```

## 拡張用型定義

### プラグイン・拡張機能
```python
class CustomEntityPattern(BaseModel):
    """カスタムエンティティパターン"""
    name: str = Field(..., min_length=1, description="パターン名")
    pattern: str = Field(..., min_length=1, description="正規表現パターン")
    entity_type: str = Field(..., min_length=1, description="エンティティ種別")
    confidence: ConfidenceScore = Field(default=0.9, description="デフォルト信頼度")
    
    @validator('pattern')
    def validate_regex_pattern(cls, v):
        try:
            import re
            re.compile(v)
        except re.error as e:
            raise ValueError(f'Invalid regex pattern: {e}')
        return v

class ProcessingPlugin(Protocol):
    """処理プラグインインターフェース"""
    
    def process_entities(
        self,
        entities: List[EntityDetection],
        config: ProcessingConfig
    ) -> List[EntityDetection]:
        """エンティティ後処理"""
        ...
    
    def get_plugin_info(self) -> Dict[str, Any]:
        """プラグイン情報取得"""
        ...
```

## mypy設定用型チェック

### 厳密型チェック設定
```python
# mypy.ini 相当の型チェック設定
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 型チェック時のみインポートする型定義
    from typing import NoReturn
    
    def assert_never(value: NoReturn) -> NoReturn:
        """網羅性チェック用"""
        raise AssertionError(f"Unhandled value: {value} ({type(value).__name__})")

# Union型の適切な処理例
def process_entity_type(entity_type: EntityType) -> str:
    """エンティティ種別の処理（網羅性チェック付き）"""
    if entity_type == "PERSON":
        return "個人名"
    elif entity_type == "LOCATION":
        return "住所"
    elif entity_type == "PHONE_NUMBER":
        return "電話番号"
    elif entity_type == "EMAIL_ADDRESS":
        return "メールアドレス"
    elif entity_type == "CREDIT_CARD":
        return "クレジットカード"
    elif entity_type == "DATE_TIME":
        return "日時"
    elif entity_type == "ORGANIZATION":
        return "組織名"
    elif entity_type == "CUSTOM":
        return "カスタム"
    else:
        if TYPE_CHECKING:
            assert_never(entity_type)
        return "不明"
```