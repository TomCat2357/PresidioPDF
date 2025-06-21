# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Japanese personal information detection and masking tool for PDF documents. The main component is `pdf_presidio_processor.py` which uses Microsoft Presidio for NLP analysis and PyMuPDF for PDF processing.

## Development Environment

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
```bash
# Install dependencies using uv (recommended)
uv sync

# Install Japanese spaCy model
uv pip install https://github.com/explosion/spacy-models/releases/download/ja_core_news_sm-3.7.0/ja_core_news_sm-3.7.0-py3-none-any.whl
uv pip install https://github.com/explosion/spacy-models/releases/download/ja_core_news_md-3.7.0/ja_core_news_md-3.7.0-py3-none-any.whl

# Install GINZA (alternative high-accuracy Japanese model)
uv run python -m pip install 'ginza[ja]'
```

### Running the processor
```bash
# Single file (using uv run)
uv run python src/pdf_presidio_processor.py document.pdf

# Folder processing
uv run python src/pdf_presidio_processor.py "C:\path\to\folder\"

# Custom suffix
uv run python src/pdf_presidio_processor.py document.pdf --suffix "_masked"

# Verbose output with new features
uv run python src/pdf_presidio_processor.py document.pdf --verbose --backup --report

# Entity selection and threshold setting
uv run python src/pdf_presidio_processor.py document.pdf --entities PERSON PHONE_NUMBER --threshold 0.8

# Custom configuration file
uv run python src/pdf_presidio_processor.py document.pdf --config my_config.yaml

# Specify spaCy model
uv run python src/pdf_presidio_processor.py document.pdf --spacy_model ja_core_news_md

# Use GINZA for enhanced Japanese processing
uv run python src/pdf_presidio_processor.py document.pdf --spacy_model ja_ginza

# Use GINZA Electra (transformer-based model for highest accuracy)
uv run python src/pdf_presidio_processor.py document.pdf --spacy_model ja_ginza_electra

# Deduplication with priority modes
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-mode score
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-mode wider_range
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-mode entity_type

# Deduplication with overlap modes
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-overlap-mode contain_only
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-overlap-mode partial_overlap

# Combined deduplication settings
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-mode score --deduplication-overlap-mode contain_only

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
- **Configurable thresholds**: Adjust confidence levels per entity type
- **Advanced deduplication**: Remove overlapping entities with configurable priority and overlap modes
  - **Priority modes**: score, wider_range, narrower_range, entity_type
  - **Overlap modes**: contain_only (containment only), partial_overlap (any overlap)
- **Backup system**: Automatic backup creation before processing
- **Detailed reporting**: JSON/text reports with processing statistics
- **Masking customization**: Configurable masking methods and annotation settings
- **Text display modes**: Control text display in masking annotations
  - **silent**: No text, color-only masking
  - **minimal**: Entity type only (e.g., "人名", "電話番号")  
  - **verbose**: Detailed information with confidence scores
- **Operation modes**: Control how annotations are handled
  - **clear_all**: Remove all existing annotations/highlights only
  - **append**: Add new annotations while preserving existing ones
  - **reset_and_append**: Remove all existing then add new annotations
- **PDF Report Restoration**: Restore PDF annotations/highlights from JSON reports
  - **Text position-based**: Highlights restored using line/character positions
  - **Coordinate-based**: Annotations restored using precise coordinates
  - **Identical duplicate removal**: Automatic removal of duplicate annotations

### Testing Infrastructure
- **Comprehensive test suite**: Mock-based testing for PDF processing dependencies
- **Multiple test scenarios**: Basic functionality, configuration, and edge cases
- **CI/CD ready**: All tests run through uv for consistency
