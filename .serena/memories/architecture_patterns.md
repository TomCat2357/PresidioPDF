# Architecture Patterns and Design Guidelines

## Core Architecture
- Modular design with clear separation of concerns
- Main orchestrator: PDFProcessor coordinates all operations
- Specialized classes for specific tasks:
  - Analyzer: PII detection with Presidio
  - PDFMasker: Text masking operations
  - PDFAnnotator: Annotation/highlight management
  - PDFTextLocator: Text coordinate location
  - ConfigManager: YAML configuration management

## Configuration Management
- YAML-based configuration with CLI override support
- Priority: CLI args > Custom config > Default config > Built-in defaults
- Support for multiple spaCy Japanese models

## Processing Modes
1. Detection & Masking: Standard workflow
2. Read Mode: Extract existing annotations (`--read-mode`)
3. Restore Mode: Restore from saved reports (`--restore-mode`)

## Multi-Model Support
- ja-core-news-sm: Lightweight (default)
- ja-core-news-md: Medium accuracy
- ja-core-news-lg: High accuracy (GPU optional)
- ja-core-news-trf: Transformer-based (highest accuracy)

## Dual Interface Design
- CLI Mode: `src/cli.py` for command-line usage
- Web Mode: `src/web_main.py` for Flask web interface