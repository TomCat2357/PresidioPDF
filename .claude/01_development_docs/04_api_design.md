# API設計

## 概要
PresidioPDFのAPI設計は、CLI、Web UI、および将来的な外部連携を考慮した内部API構造を定義する。

## アーキテクチャパターン

### API階層構造
```
├── External API Layer (Flask REST API)
├── Application Service Layer  
├── Domain Service Layer
└── Infrastructure Layer
```

### REST API 設計（Web UI用）

#### 基本エンドポイント設計
```python
# Flask APIエンドポイント設計
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ファイルアップロード
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """
    Request: multipart/form-data
    - file: PDF ファイル
    Response: {"upload_id": str, "filename": str, "size": int}
    """
    pass

# 処理実行
@app.route('/api/process', methods=['POST'])
def process_pdf():
    """
    Request: {"upload_id": str, "config": dict}
    Response: {"processing_id": str, "status": "started"}
    """
    pass

# 処理状況確認
@app.route('/api/process/<processing_id>/status', methods=['GET'])
def get_processing_status(processing_id: str):
    """
    Response: {
        "status": "processing|completed|error",
        "progress": 0-100,
        "message": str
    }
    """
    pass

# 結果取得
@app.route('/api/process/<processing_id>/result', methods=['GET'])
def get_processing_result(processing_id: str):
    """
    Response: {
        "report": ProcessingReport,
        "download_url": str
    }
    """
    pass
```

### 内部サービスAPI設計

#### PDFProcessorサービス
```python
class PDFProcessorService:
    """PDF処理のメインサービス"""
    
    async def process_pdf(
        self,
        input_file: Path,
        config: ConfigSchema,
        callback: Optional[Callable[[float], None]] = None
    ) -> ProcessingResult:
        """
        PDF処理のメインメソッド
        Args:
            input_file: 入力PDFファイルパス
            config: 処理設定
            callback: 進捗コールバック関数
        Returns:
            ProcessingResult: 処理結果
        """
        pass

    def validate_pdf(self, file_path: Path) -> ValidationResult:
        """PDFファイルの妥当性検証"""
        pass
```

#### AnalyzerService
```python
class AnalyzerService:
    """個人情報検出サービス"""
    
    def __init__(self, spacy_model: str):
        self.model = spacy_model
    
    def analyze_text(
        self,
        text: str,
        entities: List[str]
    ) -> List[EntityDetection]:
        """テキスト解析と個人情報検出"""
        pass
    
    def analyze_pdf_page(
        self,
        page_text: str,
        page_number: int
    ) -> List[EntityDetection]:
        """PDFページ単位での解析"""
        pass
```

#### MaskingService
```python
class MaskingService:
    """マスキング処理サービス"""
    
    def apply_masking(
        self,
        pdf_path: Path,
        detections: List[EntityDetection],
        method: Literal["annotation", "highlight", "both"]
    ) -> Path:
        """マスキング適用"""
        pass
    
    def restore_from_backup(
        self,
        processing_id: str
    ) -> Path:
        """バックアップからの復元"""
        pass
```

## データ転送オブジェクト（DTO）

### リクエスト/レスポンス形式

#### 処理開始リクエスト
```python
from pydantic import BaseModel
from typing import Optional, Dict, Any

class ProcessingRequest(BaseModel):
    upload_id: str
    config: Optional[Dict[str, Any]] = None
    masking_method: Optional[str] = "annotation"
    entities: Optional[Dict[str, bool]] = None
```

#### 処理結果レスポンス
```python
class ProcessingResponse(BaseModel):
    processing_id: str
    status: Literal["started", "processing", "completed", "error"]
    progress: float = 0.0
    message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
```

#### 検出結果DTO
```python
class EntityDetectionDTO(BaseModel):
    entity_type: str
    text: str
    start: int
    end: int
    confidence: float
    page: int
    coordinates: Dict[str, float]
    
    class Config:
        schema_extra = {
            "example": {
                "entity_type": "PERSON",
                "text": "田中太郎",
                "start": 100,
                "end": 104,
                "confidence": 0.95,
                "page": 1,
                "coordinates": {"x": 150, "y": 200, "width": 60, "height": 15}
            }
        }
```

## エラーハンドリング設計

### エラーレスポンス統一形式
```python
class APIError(BaseModel):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "error_code": "INVALID_FILE_FORMAT",
                "message": "アップロードされたファイルがPDF形式ではありません",
                "details": {"file_type": "image/jpeg"},
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }

# エラーコード定義
class ErrorCodes:
    INVALID_FILE_FORMAT = "INVALID_FILE_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    MODEL_LOAD_ERROR = "MODEL_LOAD_ERROR"
    INVALID_CONFIG = "INVALID_CONFIG"
```

### HTTP ステータスコードマッピング
```python
ERROR_STATUS_MAP = {
    ErrorCodes.INVALID_FILE_FORMAT: 400,
    ErrorCodes.FILE_TOO_LARGE: 413,
    ErrorCodes.PROCESSING_FAILED: 500,
    ErrorCodes.MODEL_LOAD_ERROR: 503,
    ErrorCodes.INVALID_CONFIG: 400,
}
```

## セキュリティ設計

### ファイルアップロードセキュリティ
```python
class FileUploadValidator:
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {'.pdf'}
    ALLOWED_MIME_TYPES = {'application/pdf'}
    
    def validate_upload(self, file) -> ValidationResult:
        """ファイルアップロードの検証"""
        if file.content_length > self.MAX_FILE_SIZE:
            raise FileToLargeError()
            
        if not self.is_pdf_file(file):
            raise InvalidFileFormatError()
            
        return ValidationResult(valid=True)
```

### セッション管理
```python
class SessionManager:
    def __init__(self):
        self.upload_sessions: Dict[str, UploadSession] = {}
        self.processing_sessions: Dict[str, ProcessingSession] = {}
    
    def create_upload_session(self) -> str:
        """アップロードセッション作成"""
        pass
    
    def cleanup_expired_sessions(self) -> None:
        """期限切れセッションのクリーンアップ"""
        pass
```

## レート制限とスロットリング

### 処理リソース管理
```python
class ProcessingQueue:
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self.active_processes: List[ProcessingTask] = []
        self.pending_queue: List[ProcessingTask] = []
    
    async def enqueue(self, task: ProcessingTask) -> str:
        """処理タスクをキューに追加"""
        pass
    
    async def process_queue(self) -> None:
        """キューの処理実行"""
        pass
```

## OpenAPI仕様書生成

### Swagger/OpenAPI定義
```python
from flask_restx import Api, Resource, fields

api = Api(
    title='PresidioPDF API',
    version='1.0',
    description='日本語PDF個人情報検出・マスキングAPI',
    doc='/api/doc/'
)

# モデル定義
processing_request_model = api.model('ProcessingRequest', {
    'upload_id': fields.String(required=True, description='アップロードID'),
    'config': fields.Raw(description='処理設定'),
    'masking_method': fields.String(enum=['annotation', 'highlight', 'both'])
})

processing_response_model = api.model('ProcessingResponse', {
    'processing_id': fields.String(description='処理ID'),
    'status': fields.String(enum=['started', 'processing', 'completed', 'error']),
    'progress': fields.Float(min=0, max=100),
    'message': fields.String()
})
```

## 監視・ログ設計

### API監視メトリクス
- リクエスト数とレスポンス時間
- エラー率と種別
- アクティブな処理数
- ファイルアップロード統計

### ログ設計
```python
import logging
from typing import Dict, Any

class APILogger:
    def __init__(self):
        self.logger = logging.getLogger('presidio_api')
    
    def log_request(self, endpoint: str, method: str, params: Dict[str, Any]) -> None:
        """APIリクエストログ"""
        pass
    
    def log_processing_start(self, processing_id: str, config: Dict[str, Any]) -> None:
        """処理開始ログ"""
        pass
    
    def log_processing_complete(self, processing_id: str, duration: float, stats: Dict[str, Any]) -> None:
        """処理完了ログ"""
        pass
```