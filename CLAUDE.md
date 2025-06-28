
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Japanese personal information detection and masking tool for PDF documents. The main component is `cli.py` which uses Microsoft Presidio for NLP analysis and PyMuPDF for PDF processing.

## Development Environment and Tools


### Development Environment

This project is configured to work with:
- **uv package manager**: For fast, reliable Python dependency management
- **Virtual environment**: Isolated development environment using `.venv`

The project follows modern Python development practices with uv for dependency management and virtual environment isolation.

## Core Architecture

### PDF Processing (Presidio-based)
- **PDFPresidioProcessor class**: Main processor that integrates spaCy NLP, Presidio analyzers, and PyMuPDF
- **PDFTextLocator class**: Character-level precise coordinate locator using rawdict synchronization
- **ConfigManager class**: Unified configuration management supporting YAML files and command-line arguments
- **Custom recognizers**: Japanese-specific patterns for マイナンバー (Individual Number), 年号 (Japanese Era), honorific names, and phone numbers
- **Entity masking**: Maps detected entity types to annotations or highlights in PDF documents
- **Batch processing**: Supports single files or recursive folder processing
- **Reporting system**: Generates detailed processing statistics and reports

### Precision Coordinate System
- **Character-level synchronization**: Full text and character data are perfectly synchronized using `page.get_text("rawdict")`
- **Direct offset mapping**: PII detection offsets are directly mapped to precise coordinates without search operations
- **Multi-line PII support**: Entities spanning multiple lines are accurately tracked with individual line rectangles
- **Space and newline handling**: Intelligent insertion of spaces and newlines to maintain text structure integrity


## System Requirements

- **Python 3.11+** - modern Python version required
- **uv package manager** - for fast, reliable dependency management
- **uv virtual environment** - use `.venv` for dependency isolation
- Japanese spaCy model: `ja_core_news_sm`, `ja_core_news_md`, または `ja_ginza`/`ja_ginza_electra` (GINZA)
- Dependencies managed through `pyproject.toml`



## Common Commands

### Virtual Environment Setup
```bash
# Create virtual environment (if not exists)
uv venv .venv

# Activate virtual environment
source .venv\bin\activate

# Deactivate virtual environment
deactivate
````

### Installation

#### CPUモード（デフォルト・推奨）

```bash
# 基本インストール（CPU用軽量版）
uv sync

# または、最小構成での軽量インストール
uv sync --extra minimal

# Webアプリケーション用
uv sync --extra web

# GUI用
uv sync --extra gui

# 開発用ツール含む
uv sync --extra dev

# GINZA（高精度日本語処理）を追加
uv run python -m pip install 'ginza[ja]'
```

#### GPUモード（NVIDIA CUDA環境）

```bash
# GPU対応の高精度モデルをインストール
uv sync --extra gpu

# または、CPU + GPU両方
uv sync --extra gpu --extra web --extra gui

# CUDA環境確認
nvidia-smi

# GPU動作確認
uv run python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

#### 構成オプション

  - **デフォルト（CPU）**: 軽量で安定、一般的な用途に最適
  - **GPU**: 高精度・高速処理、NVIDIA GPU必須
  - **minimal**: 最小構成、依存関係を最小限に
  - **web**: Webアプリケーション機能
  - **gui**: GUI機能
  - **dev**: 開発・テスト用ツール

### Running the processor

#### CPUモード（デフォルト）

```bash
# 基本的な単一ファイル処理
uv run python src/cli.py document.pdf

# フォルダ処理
uv run python src/cli.py "path\to\folder\"

# 詳細出力
uv run python src/cli.py document.pdf --verbose

# CPU用spaCyモデル指定
uv run python src/cli.py document.pdf --spacy_model ja_core_news_sm  # 軽量版
uv run python src/cli.py document.pdf --spacy_model ja_core_news_md  # 中サイズ版

# GINZA（CPU用高精度日本語処理）
uv run python src/cli.py document.pdf --spacy_model ja_ginza
```

#### GPUモード（高精度・高速）

```bash
# GPU用高精度モデル
uv run python src/cli.py document.pdf --spacy_model ja_core_news_lg  # 大サイズ版
uv run python src/cli.py document.pdf --spacy_model ja_core_news_trf  # Transformer版（最高精度）

# GINZA Electra（transformer版、GPU推奨）
uv run python src/cli.py document.pdf --spacy_model ja_ginza_electra


```

#### 共通オプション

```bash
# カスタム設定ファイル
uv run python src/cli.py document.pdf --config my_config.yaml

# 出力ディレクトリ指定
uv run python src/cli.py document.pdf --output-dir /path/to/output

# Deduplication with priority modes
uv run python src/cli.py document.pdf --deduplication-mode wider_range
uv run python src/cli.py document.pdf --deduplication-mode entity_type

# Deduplication with overlap modes
uv run python src/cli.py document.pdf --deduplication-overlap-mode contain_only
uv run python src/cli.py document.pdf --deduplication-overlap-mode partial_overlap

# マスキング方式と文字表示モードの指定
uv run python src/cli.py document.pdf --masking-method annotation --masking-text-mode verbose
uv run python src/cli.py document.pdf --masking-method highlight --masking-text-mode minimal
uv run python src/cli.py document.pdf --masking-method both --masking-text-mode silent

# 読み取りモード
uv run python src/cli.py document.pdf --read-mode --read-report

# 復元モード（レポートからPDFを復元）
uv run python src/cli.py original.pdf --restore-mode --report-file annotations_report_20250623_225554.json

# 操作モード指定
uv run python src/cli.py document.pdf --operation-mode clear_all        # 既存注釈を全削除
uv run python src/cli.py document.pdf --operation-mode append          # 既存注釈に追記
uv run python src/cli.py document.pdf --operation-mode reset_and_append # 全削除後に追記
```

### Testing

```bash
# Run all tests using uv
uv run pytest

# Run specific test file
uv run pytest tests/test_pdf_processor.py -v

# Run with verbose output
uv run pytest -v
```

### Web版のテスト (Playwright)

WebアプリケーションのE2E（エンドツーエンド）テストは、以下の手順を想定しています。

⓪ **既存プロセスの停止**
テストの前に、`localhost:5000` で動作している可能性のある既存のWebサーバープロセスを停止してください。

① **Webサーバーのバックグラウンド実行**
`web_main.py` をバックグラウンドプロセスとして起動します。フォアグラウンドで実行すると、後続のコマンドが実行できなくなります。

```bash
uv run python src/web_main.py &
```

②〜⑧ **Playwrightによるテスト操作**
Playwrightを使用したテストスクリプトは、以下の自動操作を実行します。

1.  `localhost:5000` に接続します。
2.  テストファイル（例: `./test_pdfs/a1.pdf`）をアップロードします。
3.  処理のために少し待機します。
4.  必要に応じて、UI上で設定を変更します。
5.  「検出開始」ボタンをクリックします。
6.  処理完了まで待機します。
7.  結果を検証するために画面のスナップショットを撮影します。

Playwrightのテストは、`pytest` 経由で実行できます。

```bash
# Webアプリケーションのテストを実行 (例)
uv run pytest tests/test_e2e_webapp.py
```

## Entity Detection & Masking

The processor detects and masks these Japanese personal information types:

  - PERSON (人名): Names and personal identifiers
  - LOCATION (場所): Addresses and location information
  - DATE\_TIME (日時): Date and time information
  - PHONE\_NUMBER (電話): Phone numbers
  - INDIVIDUAL\_NUMBER (マイナンバー): Japanese Individual Numbers
  - YEAR (年号): Japanese Era years
  - PROPER\_NOUN (固有名詞): Proper nouns and specific terms

## Testing Setup

Tests use extensive mocking due to heavy dependencies (PyMuPDF, spaCy, Presidio). The test suite provides mock fixtures for:

  - PDF document processing
  - spaCy NLP models
  - Presidio analyzer components

## File Output

Processed files are saved with configurable suffixes (default: `_masked`) in the same directory as the input file. Original files are never modified.

## Recent Development Features

### Configuration Management

  - **ConfigManager class**: Centralized configuration handling with priority system
  - **YAML configuration**: Flexible configuration through YAML files
  - **Command-line override**: CLI arguments take precedence over file configurations

### Enhanced Processing Features

  - **Selective entity detection**: Choose specific personal information types to detect
  - **Advanced deduplication**: Remove overlapping entities with configurable priority and overlap modes
      - **Priority modes**: wider\_range, narrower\_range, entity\_type
      - **Overlap modes**: contain\_only (containment only), partial\_overlap (any overlap)
  - **Backup system**: Automatic backup creation before processing
  - **Detailed reporting**: JSON/text reports with processing statistics
  - **Masking customization**: Configurable masking methods and annotation settings
  - **Text display modes**: Control text display in masking annotations
      - **silent**: No text, color-only masking
      - **minimal**: Entity type only (e.g., "人名", "電話番号")  
      - **verbose**: Detailed information with entity type and position
  - **Operation modes**: Control how annotations are handled
      - **clear\_all**: Remove all existing annotations/highlights only
      - **append**: Add new annotations while preserving existing ones
      - **reset\_and\_append**: Remove all existing then add new annotations
  - **PDF Report Restoration**: Restore PDF annotations/highlights from JSON reports
      - **Text position-based**: Highlights restored using line/character positions
      - **Coordinate-based**: Annotations restored using precise coordinates
      - **Identical duplicate removal**: Automatic removal of duplicate annotations
  - **Precision Coordinate Detection**: Character-level accurate coordinate mapping
      - **rawdict-based synchronization**: Full text and character coordinates perfectly aligned
      - **Direct offset-to-coordinate mapping**: No search operations required for coordinate detection
      - **Multi-line entity handling**: Each line of multi-line PIIs gets individual precise rectangles
      - **Space/newline reconstruction**: Intelligent text structure preservation during synchronization

### Testing Infrastructure

  - **Comprehensive test suite**: Mock-based testing for PDF processing dependencies
  - **Multiple test scenarios**: Basic functionality, configuration, and edge cases
  - **CI/CD ready**: All tests run through uv for consistency

## Technical Implementation Details

### PDFTextLocator Class Architecture

The `PDFTextLocator` class implements the core precision coordinate detection system:

```python
class PDFTextLocator:
    """
    PDF文書の文字レベル情報と、PII検出用のプレーンテキストを同期させ、
    テキストオフセットから直接、精密な座標を算出するクラス。
    """
```

**Key Methods:**

  - `_prepare_synced_data()`: Synchronizes full text with character-level coordinate data using `page.get_text("rawdict")`
  - `locate_pii_by_offset(start, end)`: Direct offset-to-coordinate mapping without search operations
  - `locate_pii(pii_text)`: Legacy method for backward compatibility (deprecated)

**Data Structures:**

  - `self.full_text`: Complete synchronized text used for PII detection
  - `self.char_data`: List of character dictionaries with precise coordinates, page, line, and block information

**Synchronization Features:**

  - Space insertion between spans based on horizontal distance thresholds
  - Newline insertion at line and block boundaries
  - Page breaks handled with appropriate newline insertion
  - Character-level rectangle information preserved for precise masking

### Integration with PDFPresidioProcessor

The processor now uses the synchronized text system:

1.  **Initialization**: Creates `PDFTextLocator` instance during PDF analysis
2.  **Text Analysis**: Uses `locator.full_text` for Presidio NLP analysis
3.  **Coordinate Mapping**: Calls `locator.locate_pii_by_offset()` with start/end offsets
4.  **Multi-line Support**: Handles entities spanning multiple lines with individual rectangles
5.  **Backward Compatibility**: Maintains `coordinates` field for legacy code

<!-- end list -->
