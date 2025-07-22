# システム設計・アーキテクチャ

## モジュール構成

### エントリーポイント
- **CLI Mode**: `src/cli.py` - コマンドライン操作
- **Web Mode**: `src/web_main.py` - Flask Webアプリケーション

### コアコンポーネント
- **PDFProcessor**: メイン制御クラス (`src/pdf_processor.py`)
- **Analyzer**: Presidio PII検出エンジン (`src/analyzer.py`)
- **PDFMasker**: PyMuPDFベース マスキング処理 (`src/pdf_masker.py`)
- **PDFAnnotator**: PDF注釈・ハイライト管理 (`src/pdf_annotator.py`)
- **PDFTextLocator**: PDF内テキスト座標検索 (`src/pdf_locator.py`)
- **ConfigManager**: YAML設定管理 (`src/config_manager.py`)

## 処理モード
1. **検出・マスキング**: 標準PII検出・マスキングワークフロー
2. **読み取りモード**: 既存注釈抽出 (`--read-mode`)
3. **復元モード**: 保存レポートからの注釈復元 (`--restore-mode`)

## 設定優先度
1. CLIオプション (`--spacy-model`, `--masking-method`)
2. カスタム設定ファイル (`--config custom.yaml`)
3. デフォルト設定ファイル (`config/config.yaml`)
4. ビルトイン設定