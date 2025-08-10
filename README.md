Presidio PDF — Japanese PII detection and masking for PDFs

Overview
- Detects Japanese PII (names, locations, dates, phone numbers, MyNumber, etc.) in PDF files using spaCy + Presidio.
- Masks detected entities by adding annotations/highlights to PDFs (PyMuPDF).
- Exports results as JSON (coordinates or text offsets) or as a highlighted PDF.

Requirements
- Python >= 3.11
- PyMuPDF, spaCy, Presidio (installed via the project dependencies)
- Japanese spaCy model: `ja_core_news_sm` (default). Larger models are optional.

Install
- Using uv (recommended):
  - `uv pip install -e .`
- Using pip:
  - `pip install -e .`

CLI Usage
- Basic: `presidio-pdf PATH [options]`
- PATH can be a single PDF file or a directory (recursive by default).

Common options
- `-c, --config PATH`        YAML config path (default: `config/config.yaml`)
- `-o, --output-dir PATH`    Output directory for generated files
- `-v, --verbose`            Enable verbose logging
- `-r, --read-mode`          Read existing highlights/annotations instead of masking
- `--read-report/--no-read-report`  Generate read report (default: on)
- `--masking-method [annotation|highlight|both]`  Masking style
- `--masking-text-mode [silent|minimal|verbose]`  Text shown in annotations
- `--operation-mode [clear_all|append|reset_and_append]`  How to apply marks
- `-E, --export-mode [1|2|3|highlight_pdf|pdf_pii_coords|text_pii_offsets]` Output mode
- `-J, --json-out PATH`      JSON output path for modes 2/3 (stdout if omitted)
- `--pretty`                 Pretty-print JSON
- `--text-variant [no_newlines|with_newlines]`   For mode 3 text extraction
- `--include-text`           Include full extracted text in mode 3 JSON
- `--exclude TEXT`           Exclude substrings (repeatable)
- `--exclude-re REGEX`       Exclude by regex (repeatable)

Export modes
1. `highlight_pdf` (default): Process and write a highlighted PDF.
2. `pdf_pii_coords`: Export JSON with per-entity page/coordinates and line rects.
3. `text_pii_offsets`: Export JSON with text offsets (optionally include full text).

Examples
- Highlight PII in a folder, write PDFs to output dir:
  - `presidio-pdf ./test_pdfs -o outputs/processed_pdfs`

- Export coordinates JSON for a single file:
  - `presidio-pdf ./test_pdfs/sample.pdf -E pdf_pii_coords -J outputs/pii_coords.json --pretty`

- Export text-offsets JSON for a directory (no newlines baseline, default):
  - `presidio-pdf ./test_pdfs -E text_pii_offsets -J outputs/text_offsets.json`

Configuration
- Default configuration lives at `config/config.yaml`.
- Command-line options override YAML. See `src/core/config_manager.py` for details.
- spaCy model defaults to `ja_core_news_sm`; larger models can be set via `--spacy-model` or YAML.

Notes
- If running in an offline environment, ensure the required spaCy model wheels are available locally or pre-installed.
- The console script is `presidio-pdf` (configured in `pyproject.toml`).

