Presidio PDF — Japanese PII detection and masking for PDFs

## Overview
- 日本語PDFの個人情報(PII)を検出し、ハイライト注釈でマスキングします。
- 実行インターフェースは **CUI** と **PyQt GUI** のみです。
- 中核処理は `read -> detect -> duplicate -> mask` の分割コマンドで構成されています。

## Requirements
- Python `>=3.11,<3.13`
- `uv` による依存管理

## Install
```bash
git clone <repository-url>
cd presidio-pdf

# 基本(CUI)依存
uv sync

# PyQt GUIを使う場合
uv sync --extra gui

# 開発用
uv sync --extra dev
```

## CUI Usage

### Command entrypoints
- `codex-read`
- `codex-detect`
- `codex-duplicate-process`
- `codex-mask`
- `codex-run-config`

上記は `uv run <entrypoint>` で実行できます。  
モジュール実行 (`uv run python -m src.cli.*`) も利用可能です。

### Basic pipeline
```bash
# 1) PDFを読み取り
uv run python -m src.cli.read_main --pdf test_pdfs/sample.pdf --out outputs/read.json --pretty --with-map

# 2) PII検出
uv run python -m src.cli.detect_main -j outputs/read.json --out outputs/detect.json --pretty

# 3) 重複整理
uv run python -m src.cli.duplicate_main -j outputs/detect.json --out outputs/deduped.json --pretty

# 4) マスキング
uv run python -m src.cli.mask_main --pdf test_pdfs/sample.pdf -j outputs/deduped.json --out outputs/masked.pdf
```

### Run from YAML config
```bash
uv run python -m src.cli.run_config_main config/sample_run.yaml
```

## PyQt GUI Usage
```bash
uv sync --extra gui
uv run presidio-gui
```

## Optional dependencies
- `dev`: pytest / black / mypy など
- `gpu`: 大規模日本語モデル・GPU関連
- `minimal`: 最小構成
- `gui`: PyQt GUI関連

## Test
```bash
uv run pytest
```

## Notes
- 依存管理は `uv` を使用してください。
- CUIコマンドの詳細は `--help` で確認できます。
  - 例: `uv run python -m src.cli.detect_main --help`
