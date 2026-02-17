# Presidio PDF — Japanese PII detection and masking for PDFs

## Overview
- 日本語PDFの個人情報(PII)を検出し、ハイライト注釈でマスキングします。
- 実行インターフェースは **CUI** と **PyQt GUI** のみです。
- 中核処理は `read -> detect -> duplicate -> mask` の分割コマンドで構成されています。

## Requirements
- Python `>=3.11,<3.12`
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

## Project Structure
```
src/
├── cli/              # CUI コマンド群
│   ├── read_main.py        # PDF読み取り
│   ├── detect_main.py      # PII検出
│   ├── duplicate_main.py   # 重複整理
│   ├── mask_main.py        # マスキング
│   ├── embed_main.py       # 埋め込み
│   ├── run_config_main.py  # YAML設定実行
│   └── common.py           # 共通ユーティリティ
├── core/             # コア処理
│   ├── config_manager.py   # 設定管理
│   ├── dedupe.py           # 重複排除ロジック
│   └── entity_types.py     # エンティティ型定義
├── pdf/              # PDF処理
│   ├── pdf_processor.py    # PDF読み取り
│   ├── pdf_masker.py       # マスキング処理
│   ├── pdf_annotator.py    # 注釈付与
│   ├── pdf_locator.py      # テキスト位置特定
│   ├── pdf_block_mapper.py # ブロックマッピング
│   ├── pdf_coordinate_mapper.py  # 座標マッピング
│   └── annotation_utils.py # 注釈ユーティリティ
├── analysis/         # 解析
│   └── analyzer.py         # Presidio Analyzer ラッパー
├── gui_pyqt/         # PyQt GUI
│   ├── main.py             # GUIエントリーポイント
│   ├── views/              # UIコンポーネント
│   │   ├── main_window.py        # メインウィンドウ
│   │   ├── pdf_preview.py        # PDFプレビュー
│   │   ├── result_panel.py       # 検出結果パネル
│   │   └── config_dialog.py      # 設定ダイアログ
│   ├── controllers/        # コントローラー
│   │   └── task_runner.py        # 非同期タスク管理
│   ├── services/           # サービス層
│   │   ├── pipeline_service.py   # パイプライン実行
│   │   └── detect_config_service.py  # 検出設定管理
│   └── models/             # データモデル
│       └── app_state.py          # アプリケーション状態
├── outputs/          # 出力管理
config/               # YAML設定ファイル
tests/                # テスト
test_pdfs/            # テスト用PDFファイル
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

### GUI機能
- **PDFドラッグ＆ドロップ**: PDFファイルをウィンドウにドロップして読み込み
- **PDFプレビュー**: 検出結果のハイライト表示
- **エクスポート機能**: 注釈付きPDF / 画像PDF / マーク画像の出力
- **ツールバーメニュー**: ドロップダウンメニューによる操作
- **対象削除**: 検出エンティティの個別削除
- **サイドカーJSON**: マッピング情報をサイドカーJSONファイルとして保存
- **未保存変更確認**: ファイル切替・終了時の確認ダイアログ

## Optional dependencies

| Extra名 | 内容 |
|---|---|
| `dev` | pytest / black / mypy など開発ツール |
| `gpu` | 大規模日本語モデル・GPU関連 |
| `minimal` | 最小構成 |
| `gui` | PyQt6 GUI関連 |
| `model-sm` | spaCy `ja-core-news-sm` モデル |
| `model-md` | spaCy `ja-core-news-md` モデル |
| `model-lg` | spaCy `ja-core-news-lg` モデル |
| `model-trf` | spaCy `ja-core-news-trf` (Transformer) モデル |
| `model-ginza-electra` | GiNZA Electra 高精度モデル |

```bash
# 例: 大規模モデルを追加
uv sync --extra model-lg

# 例: GPU + Transformer モデル
uv sync --extra gpu --extra model-trf
```

## Test
```bash
uv run pytest
```

## Notes
- 依存管理は `uv` を使用してください。
- CUIコマンドの詳細は `--help` で確認できます。
  - 例: `uv run python -m src.cli.detect_main --help`
