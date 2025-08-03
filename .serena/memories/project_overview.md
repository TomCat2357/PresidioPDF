# PresidioPDF Project Overview

## Purpose
Japanese personal information detection and masking tool for PDF documents using Microsoft Presidio. This project provides both CLI and web interfaces for PII detection and masking in PDF files.

## Tech Stack
- **Language**: Python 3.11+
- **Package Manager**: uv (not pip)
- **Core Libraries**:
  - Microsoft Presidio (PII detection)
  - spaCy with Japanese models (NLP)
  - PyMuPDF (PDF processing)
  - Flask (Web interface)
  - Playwright (Web testing)
  - pytest (Testing)
  - black (Code formatting)
  - mypy (Type checking)

## Core Components
- **PDFProcessor**: Main orchestrator (src/pdf_processor.py)
- **Analyzer**: Presidio-based PII detection (src/analyzer.py)
- **PDFMasker**: Text masking operations (src/pdf_masker.py)
- **PDFAnnotator**: Annotation/highlight management (src/pdf_annotator.py)
- **PDFTextLocator**: Text coordinate location (src/pdf_locator.py)
- **ConfigManager**: YAML configuration management (src/config_manager.py)

## Entry Points
- CLI: `src/cli.py`
- Web: `src/web_main.py`

## Project Structure
- `src/`: Source code with modular architecture
- `tests/`: Test files
- `test_pdfs/`: Sample PDF files for testing
- `outputs/`: Generated output files
- `web_uploads/`: Web app upload directory
- `.claude/`: Comprehensive documentation structure