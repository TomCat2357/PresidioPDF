# データベース設計（設定ファイル管理）

## 概要
PresidioPDFプロジェクトはローカル実行を前提としており、従来のRDBMSではなく設定ファイルとJSONベースのデータ永続化を採用する。

## データ管理方針

### 設定データ管理
YAML設定ファイルによる階層的な設定管理

```yaml
# config/config.yaml
nlp:
  spacy_model: "ja_core_news_sm"
  custom_entities: []
  confidence_threshold: 0.8

pdf_processing:
  masking_method: "annotation"  # annotation, highlight, both
  output_format: "pdf"
  preserve_original: true

entities:
  PERSON: true
  LOCATION: true
  PHONE_NUMBER: true
  EMAIL_ADDRESS: true
  CREDIT_CARD: false
```

### 処理履歴データ管理
JSON形式での処理結果とメタデータ保存

```json
{
  "processing_id": "uuid-string",
  "timestamp": "2024-01-01T12:00:00Z",
  "input_file": "path/to/input.pdf",
  "output_file": "path/to/output.pdf",
  "config_snapshot": {...},
  "detected_entities": [
    {
      "entity_type": "PERSON",
      "text": "田中太郎",
      "start": 100,
      "end": 104,
      "confidence": 0.95,
      "page": 1,
      "coordinates": {"x": 150, "y": 200, "width": 60, "height": 15}
    }
  ],
  "statistics": {
    "total_pages": 5,
    "total_entities": 15,
    "processing_time": 25.3
  }
}
```

## ディレクトリ構造

### データファイル配置
```
PresidioPDF/
├── config/
│   ├── config.yaml              # メイン設定
│   ├── config_template.yaml     # 設定テンプレート
│   └── custom/                  # カスタム設定
│       └── user_config.yaml
├── data/
│   ├── entity_patterns/         # カスタムエンティティパターン
│   │   ├── japanese_names.json
│   │   └── company_patterns.json
│   └── models/                  # spaCyモデルキャッシュ
├── outputs/
│   ├── processed/               # 処理済みPDF
│   ├── reports/                 # 処理レポート（JSON）
│   └── backups/                 # 元ファイルバックアップ
└── web_uploads/                 # Web UI一時アップロード
```

## 設定管理仕様

### 設定継承と優先順位
1. CLIパラメータ（最高優先度）
2. カスタム設定ファイル（`--config`指定）
3. ユーザー設定（`config/custom/user_config.yaml`）
4. デフォルト設定（`config/config.yaml`）

### 設定検証スキーマ
```python
from typing import Dict, List, Union, Literal
from pydantic import BaseModel, validator

class NLPConfig(BaseModel):
    spacy_model: Literal["ja_core_news_sm", "ja_core_news_md", "ja_core_news_lg", "ja_core_news_trf"]
    custom_entities: List[str] = []
    confidence_threshold: float = 0.8
    
    @validator('confidence_threshold')
    def validate_threshold(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('confidence_threshold must be between 0.0 and 1.0')
        return v

class PDFProcessingConfig(BaseModel):
    masking_method: Literal["annotation", "highlight", "both"]
    output_format: Literal["pdf", "json", "both"]
    preserve_original: bool = True

class ConfigSchema(BaseModel):
    nlp: NLPConfig
    pdf_processing: PDFProcessingConfig
    entities: Dict[str, bool]
```

## レポートデータ仕様

### 処理レポート形式
```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any

@dataclass
class EntityDetection:
    entity_type: str
    text: str
    start: int
    end: int
    confidence: float
    page: int
    coordinates: Dict[str, float]

@dataclass
class ProcessingReport:
    processing_id: str
    timestamp: datetime
    input_file: str
    output_file: str
    config_snapshot: Dict[str, Any]
    detected_entities: List[EntityDetection]
    statistics: Dict[str, Union[int, float]]
    
    def save_to_json(self, filepath: str) -> None:
        """レポートをJSONファイルに保存"""
        pass
    
    @classmethod
    def load_from_json(cls, filepath: str) -> 'ProcessingReport':
        """JSONファイルからレポートを読み込み"""
        pass
```

## データアクセスパターン

### 設定読み書き
```python
class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/config.yaml"
    
    def load_config(self) -> ConfigSchema:
        """設定を階層的に読み込み"""
        pass
    
    def validate_config(self, config: dict) -> ConfigSchema:
        """設定の妥当性検証"""
        pass
    
    def merge_cli_args(self, config: ConfigSchema, cli_args: dict) -> ConfigSchema:
        """CLI引数で設定を上書き"""
        pass
```

### レポート管理
```python
class ReportManager:
    def __init__(self, reports_dir: str = "outputs/reports"):
        self.reports_dir = Path(reports_dir)
    
    def save_report(self, report: ProcessingReport) -> str:
        """レポート保存"""
        pass
    
    def load_report(self, processing_id: str) -> ProcessingReport:
        """レポート読み込み"""
        pass
    
    def list_reports(self, limit: int = 100) -> List[ProcessingReport]:
        """レポート一覧取得"""
        pass
    
    def cleanup_old_reports(self, days: int = 30) -> int:
        """古いレポートのクリーンアップ"""
        pass
```

## バックアップ・復旧機能

### ファイルバックアップ
- 元PDFファイルの自動バックアップ
- 処理設定のスナップショット保存
- バックアップファイルの自動クリーンアップ（設定可能）

### データ整合性チェック
- 設定ファイルの形式検証
- レポートJSONの構造検証
- ファイル存在性チェック

## セキュリティ考慮事項

### データ保護
- 個人情報を含むレポートファイルの適切な権限設定
- 一時ファイルの確実な削除
- Web UIアップロードファイルの自動クリーンアップ

### アクセス制御
- 設定ファイル読み書き権限の適切な設定
- 出力ディレクトリのアクセス制限
- プロセス間での一時データ共有の最小化