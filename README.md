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
This project provides both a legacy subcommand CLI and new split commands. Prefer the new split commands for piping and tooling.

New commands (recommended)
- `codex-read`: Read a PDF and output JSON with highlights, plain text, and structured text.
- `codex-detect`: Read the JSON from `codex-read` and produce PII detections JSON (plain offsets and structured quads).
- `codex-duplicate-process`: De-duplicate detections JSON with configurable overlap/keep policies.
- `codex-mask`: Apply highlight annotations to the PDF using detections JSON.

Legacy aggregated CLI (deprecated)
- `presidio-cli <subcommand>` remains available for backward compatibility but is deprecated. Use the split commands above.

Common options
- `-v, --verbose`            Increase verbosity (repeatable)
- `--quiet`                  Suppress non-critical output
- `--config PATH`            YAML config path (default: `config/config.yaml`)

read (codex-read)
```bash
# Read a PDF into JSON (includes source, highlights, plain_text, structured_text)
uv run codex-read test_pdfs/sample.pdf --out outputs/read.json --pretty
```

detect (codex-detect)
```bash
# Detect from read JSON; writes detections with offsets/quads
uv run codex-detect --from outputs/read.json --out outputs/detect.json --pretty --validate
```

Detect additions and exclusions
- Additional entities via regex and global exclude regex are supported.
- Priority of detections: Addition > Exclude > Auto (model)
- When running detect, only the `detect` section in YAML is read; other command sections are ignored.

CLI examples
```bash
# Add regex-based detections per entity (multiple --add allowed)
uv run codex-detect --from outputs/read.json \
  --add person:"田中.*" \
  --add location:"(渋谷|新宿)" \
  --out outputs/detect.json --pretty

# Add and exclude (exclude applies only to auto/model results)
uv run codex-detect --from outputs/read.json \
  --exclude "株式会社.*" \
  --add person:"田中太郎" \
  --out outputs/detect.json --pretty

# With shared YAML config (detect section only)
uv run codex-detect --from outputs/read.json --config config/config.yaml --pretty
```

YAML (detect section; read-only)
```yaml
detect:
  - pdf: hogehoge   # placeholder, not used by detect
  - entities:
      - person: "田中太郎"
      - person: "田中健吾"
  - exclude:
      - "株式会社.*"
      - "\\d{4}-\\d{2}-\\d{2}"
```
Notes
- Allowed entity keys (lowercase): person, location, date_time, phone_number, individual_number, year, proper_noun
- Unknown entity names or invalid regex cause an error and non-zero exit

duplicate-process (codex-duplicate-process)
```bash
# De-duplicate detections with overlap/keep policies
# Overlap modes: exact (完全一致), contain (包含), overlap (一部重なり; default)
# Keep policies: widest (範囲最大; default), first, last, entity-order
uv run codex-duplicate-process \
  --detect outputs/detect.json \
  --overlap overlap \
  --keep widest \
  --out outputs/detect_dedup.json --pretty

# Entity-priority example
uv run codex-duplicate-process \
  --detect outputs/detect.json \
  --overlap overlap \
  --keep entity-order \
  --entity-priority PERSON,EMAIL,PHONE \
  --out outputs/detect_dedup.json --pretty
```

Advanced tie-break (multi-criteria)
- You can precisely control which detection is kept when overlapping.
- Criteria: origin (manual > addition > auto), length (long/short), entity (custom order), position (first/last)

CLI examples
```bash
uv run codex-duplicate-process \
  --detect outputs/detect.json \
  --overlap overlap \
  --tie-break origin,length,entity,position \
  --origin-priority manual,addition,auto \
  --length-pref long \
  --position-pref first \
  --entity-order INDIVIDUAL_NUMBER,PHONE_NUMBER,PERSON,LOCATION,DATE_TIME,YEAR,PROPER_NOUN \
  --out outputs/detect_dedup.json --pretty
```

YAML (duplicate_process section; read-only)
```yaml
duplicate_process:
  - tie_break: ["origin", "length", "entity", "position"]
  - origin_priority: ["manual", "addition", "auto"]
  - length: "long"
  - position: "first"
  - entity_order: ["INDIVIDUAL_NUMBER", "PHONE_NUMBER", "PERSON", "LOCATION", "DATE_TIME", "YEAR", "PROPER_NOUN"]
```

mask (codex-mask)
```bash
# Add highlight annotations to the PDF from detections JSON
uv run codex-mask test_pdfs/sample.pdf --detect outputs/detect_dedup.json --out outputs/sample_annotated.pdf --validate
```

Notes
- Offsets in `detect` are Unicode codepoint-based (no-newline variant used for mapping).
- Structured detection quads are in PDF user units (points).
- The previous single-command flags (e.g., `--export-mode`, `--read-mode`, `--restore-mode`, etc.) have been removed.
- `--validate` performs basic schema checks. For detections, each structured `quad` must be a 4-number array `[x0, y0, x1, y1]` and `page >= 1`.

Migration guide (legacy → split)
- `uv run presidio-cli read ...` → `uv run codex-read ...`
- `uv run presidio-cli detect ...` → `uv run codex-detect ...`
- `uv run presidio-cli duplicate-process ...` → `uv run codex-duplicate-process ...`
- `uv run presidio-cli mask ...` → `uv run codex-mask ...`

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
