# エラーハンドリング設計

## 概要
PresidioPDFにおける統一的なエラーハンドリング戦略を定義する。ユーザビリティを重視し、技術者・非技術者両方が理解しやすいエラーメッセージと適切な復旧手順を提供する。

## エラー分類体系

### エラーレベル分類
```python
from enum import Enum
from typing import Dict, Any, Optional

class ErrorLevel(Enum):
    INFO = "info"           # 情報レベル（警告）
    WARNING = "warning"     # 注意レベル（処理継続可能）
    ERROR = "error"         # エラーレベル（処理中断）
    CRITICAL = "critical"   # クリティカルレベル（システム異常）

class ErrorCategory(Enum):
    # ユーザー入力関連
    VALIDATION = "validation"
    FILE_FORMAT = "file_format" 
    FILE_SIZE = "file_size"
    
    # 処理関連
    PROCESSING = "processing"
    MODEL_LOADING = "model_loading"
    PDF_PARSING = "pdf_parsing"
    
    # システム関連
    SYSTEM = "system"
    MEMORY = "memory"
    DISK_SPACE = "disk_space"
    NETWORK = "network"
```

### エラーコード設計
```python
class ErrorCodes:
    # ファイル関連 (1000番台)
    INVALID_FILE_FORMAT = "E1001"
    FILE_TOO_LARGE = "E1002"
    FILE_CORRUPTED = "E1003"
    FILE_ENCRYPTED = "E1004"
    FILE_NOT_FOUND = "E1005"
    
    # 処理関連 (2000番台)
    MODEL_LOAD_FAILED = "E2001"
    PROCESSING_FAILED = "E2002"
    INSUFFICIENT_MEMORY = "E2003"
    PROCESSING_TIMEOUT = "E2004"
    TEXT_EXTRACTION_FAILED = "E2005"
    
    # 設定関連 (3000番台)
    INVALID_CONFIG = "E3001"
    MODEL_NOT_AVAILABLE = "E3002"
    INVALID_PARAMETER = "E3003"
    
    # システム関連 (4000番台)
    DISK_FULL = "E4001"
    PERMISSION_DENIED = "E4002"
    SYSTEM_OVERLOAD = "E4003"
    
    # Web UI関連 (5000番台)
    UPLOAD_FAILED = "E5001"
    SESSION_EXPIRED = "E5002"
    RATE_LIMIT_EXCEEDED = "E5003"

# ユーザー向けメッセージマッピング
ERROR_MESSAGES = {
    ErrorCodes.INVALID_FILE_FORMAT: {
        "user_message": "アップロードされたファイルがPDF形式ではありません。",
        "technical_message": "File format validation failed: expected PDF, got {file_type}",
        "suggestions": [
            "PDFファイルを選択してください",
            "ファイル拡張子が.pdfになっているか確認してください"
        ],
        "level": ErrorLevel.ERROR
    },
    ErrorCodes.FILE_TOO_LARGE: {
        "user_message": "ファイルサイズが制限を超えています（最大50MB）。",
        "technical_message": "File size {size}MB exceeds maximum limit of {max_size}MB",
        "suggestions": [
            "PDFを分割してより小さなファイルにしてください",
            "画像の解像度を下げてファイルサイズを縮小してください"
        ],
        "level": ErrorLevel.ERROR
    }
}
```

## エラーハンドリング基盤

### 基底例外クラス
```python
class PresidioPDFError(Exception):
    """PresidioPDF基底例外クラス"""
    
    def __init__(
        self,
        error_code: str,
        message: str = None,
        details: Dict[str, Any] = None,
        cause: Exception = None
    ):
        self.error_code = error_code
        self.message = message or ERROR_MESSAGES.get(error_code, {}).get("user_message", "Unknown error")
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.utcnow()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式でエラー情報を返す"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "level": ERROR_MESSAGES.get(self.error_code, {}).get("level", ErrorLevel.ERROR).value
        }

# 具体的なエラークラス
class FileValidationError(PresidioPDFError):
    """ファイル検証エラー"""
    pass

class ProcessingError(PresidioPDFError):
    """処理エラー"""
    pass

class ModelLoadError(PresidioPDFError):
    """モデル読み込みエラー"""
    pass

class SystemError(PresidioPDFError):
    """システムエラー"""
    pass
```

### エラーハンドリングデコレータ
```python
from functools import wraps
import logging

def handle_errors(
    default_error_code: str = "E4000",
    log_level: int = logging.ERROR
):
    """エラーハンドリングデコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except PresidioPDFError:
                # 既知のエラーはそのまま再raise
                raise
            except FileNotFoundError as e:
                raise FileValidationError(
                    ErrorCodes.FILE_NOT_FOUND,
                    details={"file_path": str(e.filename)},
                    cause=e
                )
            except MemoryError as e:
                raise SystemError(
                    ErrorCodes.INSUFFICIENT_MEMORY,
                    cause=e
                )
            except Exception as e:
                # 予期しないエラーはログに記録してシステムエラーとして処理
                logging.log(log_level, f"Unexpected error in {func.__name__}: {str(e)}", exc_info=True)
                raise SystemError(
                    default_error_code,
                    details={"function": func.__name__, "args": str(args)},
                    cause=e
                )
        return wrapper
    return decorator
```

## CLI用エラーハンドリング

### CLI エラー表示
```python
import click
from colorama import Fore, Style

class CLIErrorHandler:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def handle_error(self, error: PresidioPDFError) -> None:
        """CLIでのエラーハンドリング"""
        # エラーメッセージの表示
        click.echo(f"{Fore.RED}エラー: {error.message}{Style.RESET_ALL}")
        
        # 改善提案の表示
        suggestions = ERROR_MESSAGES.get(error.error_code, {}).get("suggestions", [])
        if suggestions:
            click.echo(f"{Fore.YELLOW}改善案:{Style.RESET_ALL}")
            for suggestion in suggestions:
                click.echo(f"  • {suggestion}")
        
        # 詳細情報（verboseモード時）
        if self.verbose:
            click.echo(f"{Fore.CYAN}詳細情報:{Style.RESET_ALL}")
            click.echo(f"  エラーコード: {error.error_code}")
            click.echo(f"  発生時刻: {error.timestamp}")
            if error.details:
                for key, value in error.details.items():
                    click.echo(f"  {key}: {value}")
        
        # 技術的詳細（デバッグモード時）
        if self.verbose and error.cause:
            click.echo(f"{Fore.MAGENTA}技術的詳細:{Style.RESET_ALL}")
            click.echo(f"  {type(error.cause).__name__}: {str(error.cause)}")

# 使用例
@click.command()
@click.option('--verbose', is_flag=True, help='詳細なエラー情報を表示')
def process_pdf(file_path: str, verbose: bool):
    error_handler = CLIErrorHandler(verbose)
    
    try:
        # PDF処理実行
        result = process_pdf_file(file_path)
        click.echo(f"処理完了: {result}")
    except PresidioPDFError as e:
        error_handler.handle_error(e)
        sys.exit(1)
```

## Web UI用エラーハンドリング

### Flask エラーハンドラー
```python
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

@app.errorhandler(PresidioPDFError)
def handle_presidio_error(error: PresidioPDFError):
    """PresidioPDF固有エラーのハンドリング"""
    
    # APIリクエストの場合はJSON形式で返す
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({
            "error": error.to_dict(),
            "suggestions": ERROR_MESSAGES.get(error.error_code, {}).get("suggestions", [])
        }), get_http_status_code(error.error_code)
    
    # 通常のWebリクエストの場合はHTMLエラーページ
    return render_template(
        'error.html',
        error=error,
        suggestions=ERROR_MESSAGES.get(error.error_code, {}).get("suggestions", [])
    ), get_http_status_code(error.error_code)

@app.errorhandler(413)  # Request Entity Too Large
def handle_file_too_large(e):
    """ファイルサイズ超過エラー"""
    error = FileValidationError(ErrorCodes.FILE_TOO_LARGE)
    return handle_presidio_error(error)

@app.errorhandler(500)
def handle_internal_error(e):
    """内部サーバーエラー"""
    error = SystemError("E4000", "予期しないエラーが発生しました")
    return handle_presidio_error(error)

def get_http_status_code(error_code: str) -> int:
    """エラーコードからHTTPステータスコードを取得"""
    status_map = {
        ErrorCodes.INVALID_FILE_FORMAT: 400,
        ErrorCodes.FILE_TOO_LARGE: 413,
        ErrorCodes.FILE_NOT_FOUND: 404,
        ErrorCodes.INVALID_CONFIG: 400,
        ErrorCodes.PROCESSING_TIMEOUT: 408,
        ErrorCodes.SYSTEM_OVERLOAD: 503,
        ErrorCodes.INSUFFICIENT_MEMORY: 503,
    }
    return status_map.get(error_code, 500)
```

### JavaScript フロントエンドエラーハンドリング
```javascript
class ErrorHandler {
    constructor() {
        this.errorContainer = document.getElementById('error-container');
    }
    
    displayError(error) {
        const errorData = error.error || error;
        
        // エラーメッセージの表示
        const errorHTML = `
            <div class="error-alert alert-${this.getAlertClass(errorData.level)}">
                <h4>エラーが発生しました</h4>
                <p>${errorData.message}</p>
                ${this.renderSuggestions(error.suggestions)}
                <button onclick="this.parentElement.style.display='none'">閉じる</button>
            </div>
        `;
        
        this.errorContainer.innerHTML = errorHTML;
        this.errorContainer.style.display = 'block';
        
        // エラーレポート送信（オプション）
        if (errorData.level === 'critical') {
            this.reportError(errorData);
        }
    }
    
    renderSuggestions(suggestions) {
        if (!suggestions || suggestions.length === 0) return '';
        
        return `
            <div class="error-suggestions">
                <h5>改善案:</h5>
                <ul>
                    ${suggestions.map(s => `<li>${s}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    getAlertClass(level) {
        const classMap = {
            'info': 'info',
            'warning': 'warning', 
            'error': 'danger',
            'critical': 'danger'
        };
        return classMap[level] || 'danger';
    }
    
    reportError(errorData) {
        // 重大なエラーの場合、サーバーに自動レポート
        fetch('/api/error-report', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                error: errorData,
                user_agent: navigator.userAgent,
                url: window.location.href,
                timestamp: new Date().toISOString()
            })
        });
    }
}

// グローバルエラーハンドラーの設定
const errorHandler = new ErrorHandler();

// Fetch APIエラーハンドリング
async function handleApiCall(url, options = {}) {
    try {
        const response = await fetch(url, options);
        const data = await response.json();
        
        if (!response.ok) {
            errorHandler.displayError(data);
            throw new Error(data.error?.message || 'API error');
        }
        
        return data;
    } catch (error) {
        if (error.name === 'TypeError') {
            // ネットワークエラー
            errorHandler.displayError({
                error: {
                    message: 'ネットワークエラーが発生しました。インターネット接続を確認してください。',
                    level: 'error'
                }
            });
        }
        throw error;
    }
}
```

## ログ設計

### 構造化ログ出力
```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
        # ログフォーマット設定
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # ファイルハンドラー
        file_handler = logging.FileHandler('logs/presidio_errors.log')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        self.logger.setLevel(logging.INFO)
    
    def log_error(self, error: PresidioPDFError, context: Dict[str, Any] = None):
        """エラーログの構造化記録"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_code": error.error_code,
            "message": error.message,
            "details": error.details,
            "level": ERROR_MESSAGES.get(error.error_code, {}).get("level", ErrorLevel.ERROR).value,
            "context": context or {}
        }
        
        if error.cause:
            log_data["cause"] = {
                "type": type(error.cause).__name__,
                "message": str(error.cause)
            }
        
        self.logger.error(json.dumps(log_data, ensure_ascii=False))
    
    def log_processing_error(self, file_path: str, error: Exception, processing_config: dict):
        """処理エラーの詳細ログ"""
        context = {
            "file_path": file_path,
            "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            "config": processing_config,
            "system_info": {
                "memory_usage": psutil.virtual_memory().percent,
                "cpu_usage": psutil.cpu_percent()
            }
        }
        self.log_error(error, context)
```

## エラー監視・アラート

### 基本監視設定
```python
class ErrorMonitor:
    def __init__(self):
        self.error_counts = defaultdict(int)
        self.last_reset = datetime.utcnow()
    
    def record_error(self, error_code: str):
        """エラー発生をカウント"""
        self.error_counts[error_code] += 1
        
        # クリティカルエラーの即座アラート
        if ERROR_MESSAGES.get(error_code, {}).get("level") == ErrorLevel.CRITICAL:
            self.send_alert(error_code)
        
        # 大量エラー検知
        if self.error_counts[error_code] > 10:  # 閾値
            self.send_mass_error_alert(error_code)
    
    def send_alert(self, error_code: str):
        """アラート送信（実装は環境依存）"""
        pass
    
    def get_error_stats(self) -> Dict[str, int]:
        """エラー統計取得"""
        return dict(self.error_counts)
```

## ユーザー向けエラー回復支援

### 自動復旧機能
```python
class ErrorRecovery:
    def __init__(self):
        self.recovery_strategies = {
            ErrorCodes.MODEL_LOAD_FAILED: self.recover_model_load,
            ErrorCodes.INSUFFICIENT_MEMORY: self.recover_memory_issue,
            ErrorCodes.PROCESSING_TIMEOUT: self.recover_timeout
        }
    
    def attempt_recovery(self, error: PresidioPDFError) -> Optional[Any]:
        """エラーからの自動復旧を試行"""
        strategy = self.recovery_strategies.get(error.error_code)
        if strategy:
            return strategy(error)
        return None
    
    def recover_model_load(self, error: PresidioPDFError):
        """spaCyモデル読み込みエラーからの復旧"""
        # より軽量なモデルで再試行
        return "ja_core_news_sm"  # デフォルトに戻す
    
    def recover_memory_issue(self, error: PresidioPDFError):
        """メモリ不足エラーからの復旧"""
        # バッチサイズを縮小して再試行
        return {"batch_size": 1, "optimize_memory": True}
```