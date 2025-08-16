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
- `codex-read`: Read a PDF and output JSON with text and coordinate mapping data.
- `codex-detect`: Read the JSON from `codex-read` and produce PII detections JSON in specification format.
- `codex-duplicate-process`: De-duplicate detections JSON with configurable overlap/keep policies including entity-aware processing.
- `codex-mask`: Apply highlight annotations to the PDF using detections JSON with optional coordinate map embedding.
- `uv run python -m src.cli.embed_main`: Embed coordinate mapping data into PDF documents.

Legacy aggregated CLI (deprecated)
- `presidio-cli <subcommand>` remains available for backward compatibility but is deprecated. Use the split commands above.

Common options
- `-v, --verbose`            Increase verbosity (repeatable)
- `--quiet`                  Suppress non-critical output
- `--config PATH`            YAML config path (default: `config/config.yaml`)

read (codex-read)
```bash
# Read a PDF into JSON (specification format: text as 2D array, optional coordinate maps)
uv run codex-read --pdf test_pdfs/sample.pdf --out outputs/read.json --pretty --with-map

# Read with embedded coordinate maps from processed PDFs
uv run codex-read --pdf processed.pdf --out outputs/read.json --pretty --with-map

# Read existing highlights from PDF
uv run codex-read --pdf test_pdfs/sample.pdf --out outputs/read.json --pretty --with-highlights
```

New options:
- `--with-map/--no-map`: Include coordinate mapping data (default: True)
- `--with-highlights`: Include existing PDF highlights in detect field

detect (codex-detect)
```bash
# Detect from read JSON; writes detections in specification format (page_num/block_num/offset)
uv run codex-detect -j outputs/read.json --out outputs/detect.json --pretty --validate

# Include existing detections from read result
uv run codex-detect -j outputs/read.json --out outputs/detect.json --with-predetect

# Exclude existing detections (replace mode)
uv run codex-detect -j outputs/read.json --out outputs/detect.json --no-predetect
```

New options:
- `--with-predetect/--no-predetect`: Include existing detect information from input (default: True)

Detect additions and exclusions
- Additional entities via regex and global exclude regex are supported.
- Priority of detections: Addition > Exclude > Auto (model)
- When running detect, only the `detect` section in YAML is read; other command sections are ignored.

CLI examples
```bash
# Add regex-based detections per entity (multiple --add allowed)
uv run codex-detect -j outputs/read.json \
  --add person:"田中.*" \
  --add location:"(渋谷|新宿)" \
  --out outputs/detect.json --pretty

# Add and exclude (exclude applies only to auto/model results)
uv run codex-detect -j outputs/read.json \
  --exclude "株式会社.*" \
  --add person:"田中太郎" \
  --out outputs/detect.json --pretty

# With shared YAML config (detect section only)
uv run codex-detect -j outputs/read.json --config config/config.yaml --out outputs/detect.json --pretty
```

duplicate (codex-duplicate-process)
```bash
# Basic duplicate processing
uv run codex-duplicate-process -j outputs/detect.json --out outputs/deduped.json --pretty

# Entity-aware duplicate processing (same entity types only)
uv run codex-duplicate-process -j outputs/detect.json --out outputs/deduped.json \
  --entity-overlap-mode same --pretty

# Cross-entity duplicate processing (different entity types can be duplicates)
uv run codex-duplicate-process -j outputs/detect.json --out outputs/deduped.json \
  --entity-overlap-mode any --pretty
```

New options:
- `--entity-overlap-mode`: Control entity type consideration in duplicate processing
  - `same`: Only same entity types are considered for overlap (default)
  - `any`: Different entity types can also be considered for overlap

mask (codex-mask)
```bash
# Basic PDF masking
uv run codex-mask --pdf input.pdf -j outputs/detect.json --out masked.pdf

# Embed coordinate maps in output PDF
uv run codex-mask --pdf input.pdf -j outputs/detect.json --out masked.pdf \
  --embed-coordinates

# Read embedded coordinate maps from the masked PDF
uv run codex-read --pdf masked.pdf --out extracted.json --with-map
```

New options:
- `--embed-coordinates/--no-embed-coordinates`: Embed coordinate mapping data in output PDF (default: False)

embed (embed_main.py)
```bash
# Embed coordinate maps from JSON into PDF
uv run python -m src.cli.embed_main --pdf input.pdf -j outputs/read.json --out embedded.pdf

# Force embedding even if hash mismatch
uv run python -m src.cli.embed_main --pdf input.pdf -j outputs/read.json --out embedded.pdf --force
```

Options:
- `--pdf`: Input PDF file path (required)
- `-j, --json`: JSON file containing coordinate mapping data (required) 
- `--out`: Output PDF path (required)
- `--config`: Configuration file path (optional)
- `--force`: Force embedding even if PDF hash doesn't match JSON metadata

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

JSON Output Format

The new specification uses a simplified JSON format:

**read output:**
```json
{
  "metadata": {
    "pdf": {
      "filename": "document.pdf",
      "path": "/absolute/path/to/document.pdf",
      "size": 12345,
      "page_count": 3,
      "sha256": "abc123...",
      "created_at": "2023-01-01T00:00:00",
      "modified_at": "2023-01-01T00:00:00"
    },
    "generated_at": "2023-01-01T00:00:00Z"
  },
  "text": [
    ["page0_block0_text", "page0_block1_text"],
    ["page1_block0_text", "page1_block1_text"],
    ["page2_block0_text"]
  ],
  "detect": [
    {
      "start": {"page_num": 0, "block_num": 0, "offset": 5},
      "end": {"page_num": 0, "block_num": 0, "offset": 8},
      "entity": "PERSON",
      "word": "田中太郎",
      "origin": "manual"
    }
  ],
  "offset2coordsMap": {
    "0": {
      "0": [[100, 200, 150, 220], [160, 200, 200, 220]]
    }
  },
  "coords2offsetMap": {
    "(100,200,150,220)": "(0,0,0)",
    "(160,200,200,220)": "(0,0,4)"
  }
}
```

**detect output:**
```json
{
  "metadata": { /* same as read */ },
  "detect": [
    {
      "start": {"page_num": 0, "block_num": 0, "offset": 5},
      "end": {"page_num": 0, "block_num": 0, "offset": 8},
      "entity": "PERSON",
      "word": "田中太郎", 
      "origin": "auto"
    }
  ],
  "offset2coordsMap": { /* inherited from read */ },
  "coords2offsetMap": { /* inherited from read */ }
}
```

Key changes:
- `text`: 2D array format `[["block1", "block2"], ["page2_block1"]]`
- `detect`: Flat array with `start`/`end` as `{page_num, block_num, offset}` objects
- `offset2coordsMap`: Maps page/block positions to coordinate arrays
- `coords2offsetMap`: Maps coordinates to position tuples

Legacy duplicate-process (codex-duplicate-process)
```bash
# De-duplicate detections with overlap/keep policies  
# Overlap modes: exact (完全一致), contain (包含), overlap (一部重なり; default)
# Keep policies: widest (範囲最大; default), first, last, entity-order
uv run codex-duplicate-process \
  -j outputs/detect.json \
  --overlap overlap \
  --keep widest \
  --out outputs/detect_dedup.json --pretty

# Entity-priority example
uv run codex-duplicate-process \
  -j outputs/detect.json \
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
uv run codex-mask --pdf test_pdfs/sample.pdf -j outputs/detect_dedup.json --out outputs/sample_annotated.pdf --validate
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
- Mask hash mismatch: `codex-mask ...` fails with sha256 mismatch
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
- Console scripts: `codex-read`, `codex-detect`, `codex-duplicate-process`, `codex-mask` (CLI), `presidio-web` (Web UI)
