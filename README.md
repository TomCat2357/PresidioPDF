Presidio PDF — Japanese PII detection and masking for PDFs

Overview
- Detects Japanese PII (names, locations, dates, phone numbers, MyNumber, etc.) in PDF files using spaCy + Presidio.
- Masks detected entities by adding annotations/highlights to PDFs (PyMuPDF).
- Exports results as JSON (coordinates or text offsets) or as a highlighted PDF.
- Provides both CLI and Web UI interfaces with advanced features.

Requirements
- Python >= 3.11
- Dependencies managed via `uv` package manager
- Japanese spaCy model: `ja_core_news_sm` (default). Larger models available with optional dependencies.

Install
Using `uv` (recommended):
```bash
# Clone the repository
git clone <repository-url>
cd presidio-pdf

# Install with default dependencies (CPU mode)
uv sync

# Install with optional dependencies
uv sync --extra dev        # Development tools
uv sync --extra gpu        # GPU-optimized models (ja_core_news_md, ja_core_news_lg)
uv sync --extra web        # Web application dependencies
uv sync --extra gui        # Desktop GUI dependencies
uv sync --extra minimal    # Minimal installation
```

Note: This project exclusively uses `uv` for dependency management. Do not use `pip`.

CLI Usage
This project now uses subcommands. Run `presidio-cli --help` for an overview, or `presidio-cli <subcommand> --help` for details.

Subcommands
- `read`: Read a PDF and output JSON with highlights, plain text, and structured text.
- `detect`: Read the JSON from `read` and produce PII detections JSON (plain offsets and structured quads).
- `duplicate-process`: De-duplicate detections JSON.
- `mask`: Apply highlight annotations to the PDF using detections JSON.

Common options
- `-v, --verbose`            Increase verbosity (repeatable)
- `--quiet`                  Suppress non-critical output
- `--config PATH`            YAML config path (default: `config/config.yaml`)

read
```bash
# Read a PDF into JSON (includes source, highlights, plain_text, structured_text)
uv run presidio-cli read test_pdfs/sample.pdf --out outputs/read.json --pretty
```

detect
```bash
# Detect from read JSON; writes detections with offsets/quads
uv run presidio-cli detect --from outputs/read.json --out outputs/detect.json --pretty --validate
```

duplicate-process
```bash
# Remove duplicate detections (simple first-wins policy)
uv run presidio-cli duplicate-process --detect outputs/detect.json --out outputs/detect_dedup.json --pretty
```

mask
```bash
# Add highlight annotations to the PDF from detections JSON
uv run presidio-cli mask test_pdfs/sample.pdf --detect outputs/detect_dedup.json --out outputs/sample_annotated.pdf --validate
```

Notes
- Offsets in `detect` are Unicode codepoint-based (no-newline variant used for mapping).
- Structured detection quads are in PDF user units (points).
- The previous single-command flags (e.g., `--export-mode`, `--read-mode`, `--restore-mode`, etc.) have been removed.
- `--validate` performs basic schema checks. For detections, each structured `quad` must be a 4-number array `[x0, y0, x1, y1]` and `page >= 1`.

JSON Schemas (concise)
- `read` output
  - `schema_version: string`, `generated_at: RFC3339-Z`
  - `source: { filename, path, size, page_count, sha256, created_at, modified_at }`
  - `content:`
    - `highlight: Array<object>` existing PDF annotations (page/rect/info)
    - `plain_text: string|null` single string without newlines used for offset mapping
    - `structured_text: { pages: [ { page: number, blocks: [ { lines: [ { spans: [ { text, bbox } ] } ] } ] } ] }`

- `detect` output
  - `schema_version: string`, `generated_at: RFC3339-Z`
  - `source: { pdf: { sha256 }, read_json_sha256 }`
  - `detections:`
    - `plain: [ { detection_id, text, entity, start, end, unit:"codepoint", origin:"model", model_id?, confidence? } ]`
    - `structured: [ { detection_id, text, entity, page, quads: [ [x0,y0,x1,y1], ... ], origin:"model", model_id?, confidence? } ]`
  - `highlights?: Array<object>` passthrough of `read.content.highlight` when `--append-highlights`

Troubleshooting
- Mask hash mismatch: `presidio-cli mask ...` fails with sha256 mismatch
  - Ensure the PDF used for `mask` matches the PDF in `read`/`detect`. Use `--force` to override (not recommended).
- Missing `source.path` in detect input
  - Use the `read` subcommand’s output as input to `detect`. It includes absolute `source.path`.
- spaCy model errors
  - Install `ja_core_news_sm` via the project’s `uv sync`. For larger models, install extras (gpu) as needed.
- Large PDFs or timeouts
  - Detection runs in-memory; very large PDFs can be slow. Consider splitting the document or running on a machine with more memory/CPU.

Web UI
Launch the web application:
```bash
# Start web server (CPU mode, default port 5000)
uv run presidio-web

# Start with GPU support
uv run presidio-web --gpu

# Custom host and port
uv run presidio-web --host 127.0.0.1 --port 8080 --debug
```

Web UI Features:
- **PDF Upload**: Drag-and-drop or click to upload PDF files (up to 50MB)
- **Model Selection**: Choose from ja_core_news_sm/md/lg/trf models
- **Entity Configuration**: Enable/disable detection for specific entity types
- **Advanced Settings**:
  - Masking method (highlight/annotation/both)
  - Text display mode (silent/minimal/verbose)
  - Deduplication settings
- **Pattern Management**:
  - Exclusion patterns: Regex patterns to exclude from detection
  - Additional patterns: Custom regex rules per entity type
- **Manual Editing**: Add/remove PII entities directly in the PDF viewer
- **Export Options**: Download masked PDFs with highlights/annotations

Web UI Options:
- `--gpu`               Enable GPU mode with NVIDIA CUDA support
- `--host HOST`         Server host address (default: 0.0.0.0)
- `--port PORT`         Server port number (default: 5000)
- `--debug`             Enable debug mode with auto-reload

Configuration
- Default configuration: `config/config.yaml`
- Template configuration: `config/config_template.yaml`
- Test configuration: `config/test_config.yaml`
- Command-line options override YAML settings
- Web UI settings are session-based and override both CLI and YAML
- spaCy model defaults to `ja_core_news_sm`; larger models available with `--extra gpu`

Optional Dependencies
- **dev**: Development tools (pytest, black, mypy, playwright)
- **gpu**: High-accuracy models (ja_core_news_md/lg, torch, pandas)
- **minimal**: Lightweight installation with basic functionality
- **web**: Web application dependencies (Flask, requests)
- **gui**: Desktop GUI dependencies (FreeSimpleGUI, Pillow)

Notes
- This project uses `uv` exclusively for dependency management
- For offline environments, ensure spaCy model wheels are pre-installed
- Web UI provides additional features not available in CLI mode
- Console scripts: `presidio-cli` (CLI), `presidio-web` (Web UI)
