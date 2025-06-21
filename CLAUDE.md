# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Japanese personal information detection and masking tool for PDF documents. The main component is `pdf_presidio_processor.py` which uses Microsoft Presidio for NLP analysis and PyMuPDF for PDF processing.

## Development Environment and Tools

### Desktop Commander Usage
When working with this project, use the desktop-commander MCP server for file operations and command execution.

**Project Root Directory:**
```
C:\Users\gk3t-\OneDrive - 又村 友幸\working\PresidioPDF
```

**Important Notes:**
- Always start desktop-commander operations by running `pwd` to confirm the current working directory
- Use absolute paths when working with desktop-commander tools
- The project root should be set to the path above for consistent file operations

### Desktop Commander Commands Reference
- `mcp__desktop-commander__execute_command`: Execute terminal commands
- `mcp__desktop-commander__read_file`: Read file contents with offset/length support
- `mcp__desktop-commander__write_file`: Write files in chunks (recommended: 25-30 lines max)
- `mcp__desktop-commander__edit_block`: Make surgical text replacements
- `mcp__desktop-commander__search_code`: Search for text patterns in code
- `mcp__desktop-commander__search_files`: Find files by name patterns
- `mcp__desktop-commander__list_directory`: List directory contents

### Development Environment

This project is configured to work with:
- **uv package manager**: For fast, reliable Python dependency management
- **Virtual environment**: Isolated development environment using `.venv`

The project follows modern Python development practices with uv for dependency management and virtual environment isolation.

## Core Architecture

### PDF Processing (Presidio-based)
- **PDFPresidioProcessor class**: Main processor that integrates spaCy NLP, Presidio analyzers, and PyMuPDF
- **ConfigManager class**: Unified configuration management supporting YAML files and command-line arguments
- **Custom recognizers**: Japanese-specific patterns for マイナンバー (Individual Number), 年号 (Japanese Era), honorific names, and phone numbers
- **Entity masking**: Maps detected entity types to annotations or highlights in PDF documents
- **Batch processing**: Supports single files or recursive folder processing
- **Reporting system**: Generates detailed processing statistics and reports


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
```

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
uv run python src/pdf_presidio_processor.py document.pdf

# フォルダ処理
uv run python src/pdf_presidio_processor.py "path\to\folder\"

# 詳細出力とバックアップ・レポート機能
uv run python src/pdf_presidio_processor.py document.pdf --verbose --backup --report

# CPU用spaCyモデル指定
uv run python src/pdf_presidio_processor.py document.pdf --spacy_model ja_core_news_sm  # 軽量版
uv run python src/pdf_presidio_processor.py document.pdf --spacy_model ja_core_news_md  # 中サイズ版

# GINZA（CPU用高精度日本語処理）
uv run python src/pdf_presidio_processor.py document.pdf --spacy_model ja_ginza
```

#### GPUモード（高精度・高速）
```bash
# GPU用高精度モデル
uv run python src/pdf_presidio_processor.py document.pdf --spacy_model ja_core_news_lg  # 大サイズ版
uv run python src/pdf_presidio_processor.py document.pdf --spacy_model ja_core_news_trf  # Transformer版（最高精度）

# GINZA Electra（transformer版、GPU推奨）
uv run python src/pdf_presidio_processor.py document.pdf --spacy_model ja_ginza_electra

# GPU モードで実行（明示的指定）
uv run python src/pdf_presidio_processor.py document.pdf --gpu --spacy_model ja_core_news_trf

# CPU強制モード（GPUが利用可能でもCPUを使用）
uv run python src/pdf_presidio_processor.py document.pdf --cpu --spacy_model ja_core_news_md
```

#### 共通オプション
```bash
# エンティティ選択
uv run python src/pdf_presidio_processor.py document.pdf --entities PERSON PHONE_NUMBER

# カスタム設定ファイル
uv run python src/pdf_presidio_processor.py document.pdf --config my_config.yaml

# カスタムサフィックス
uv run python src/pdf_presidio_processor.py document.pdf --suffix "_masked"

# Deduplication with priority modes
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-mode wider_range
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-mode entity_type

# Deduplication with overlap modes
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-overlap-mode contain_only
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-overlap-mode partial_overlap

# マスキング方式と文字表示モードの指定
uv run python src/pdf_presidio_processor.py document.pdf --masking-method annotation --masking-text-mode verbose
uv run python src/pdf_presidio_processor.py document.pdf --masking-method highlight --masking-text-mode minimal
uv run python src/pdf_presidio_processor.py document.pdf --masking-method both --masking-text-mode silent

# 読み取りモード
uv run python src/pdf_presidio_processor.py document.pdf --read-mode --read-report

# 復元モード（レポートからPDFを復元）
uv run python src/pdf_presidio_processor.py original.pdf --restore-mode --report-file annotations_report_20241215_143052.json

# 操作モード指定
uv run python src/pdf_presidio_processor.py document.pdf --operation-mode clear_all        # 既存注釈を全削除
uv run python src/pdf_presidio_processor.py document.pdf --operation-mode append          # 既存注釈に追記
uv run python src/pdf_presidio_processor.py document.pdf --operation-mode reset_and_append # 全削除後に追記
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

## Entity Detection & Masking

The processor detects and masks these Japanese personal information types:
- PERSON (人名): Names and personal identifiers
- LOCATION (場所): Addresses and location information
- DATE_TIME (日時): Date and time information
- PHONE_NUMBER (電話): Phone numbers
- INDIVIDUAL_NUMBER (マイナンバー): Japanese Individual Numbers
- YEAR (年号): Japanese Era years
- PROPER_NOUN (固有名詞): Proper nouns and specific terms

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
  - **Priority modes**: wider_range, narrower_range, entity_type
  - **Overlap modes**: contain_only (containment only), partial_overlap (any overlap)
- **Backup system**: Automatic backup creation before processing
- **Detailed reporting**: JSON/text reports with processing statistics
- **Masking customization**: Configurable masking methods and annotation settings
- **Text display modes**: Control text display in masking annotations
  - **silent**: No text, color-only masking
  - **minimal**: Entity type only (e.g., "人名", "電話番号")  
  - **verbose**: Detailed information with entity type and position
- **Operation modes**: Control how annotations are handled
  - **clear_all**: Remove all existing annotations/highlights only
  - **append**: Add new annotations while preserving existing ones
  - **reset_and_append**: Remove all existing then add new annotations
- **PDF Report Restoration**: Restore PDF annotations/highlights from JSON reports
  - **Text position-based**: Highlights restored using line/character positions
  - **Coordinate-based**: Annotations restored using precise coordinates
  - **Identical duplicate removal**: Automatic removal of duplicate annotations
- **Enhanced Position Information**: Detailed location tracking with page, line, and character positions
  - **Page-level positioning**: Track which page contains each entity
  - **Line-level positioning**: Track line numbers within pages
  - **Character-level positioning**: Track character positions within lines
  - **Multi-page/multi-line support**: Handle entities spanning multiple pages or lines

### Testing Infrastructure
- **Comprehensive test suite**: Mock-based testing for PDF processing dependencies
- **Multiple test scenarios**: Basic functionality, configuration, and edge cases
- **CI/CD ready**: All tests run through uv for consistency

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.