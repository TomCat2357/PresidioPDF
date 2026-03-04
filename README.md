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

# OCR機能（NDLOCR-Lite）も使う場合
uv sync --extra gui --extra ocr

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

OCR機能を有効化する場合:
```bash
uv sync --extra gui --extra ocr
uv run presidio-gui
```

### GUI機能

#### 基本操作
- **PDFドラッグ＆ドロップ**: PDFファイルをウィンドウにドロップして読み込み
- **PDFプレビュー**: 検出結果のハイライト表示（クリックで対応行にフォーカス移動）
- **PDFを閉じる**: ツールバー「閉じる」ボタンで現在のPDFを閉じる
- **未保存変更確認**: ファイル切替・終了時の確認ダイアログ
- **サイドカーJSON**: マッピング情報をサイドカーJSONファイルとして保存

#### ツールバー
| ボタン | 機能 |
|--------|------|
| 開く | PDFファイルを開く（マッピングがあれば自動読込） |
| 閉じる | 現在のPDFを閉じる |
| 設定 | 検出・重複排除設定ダイアログを開く |
| 📖 Read | PDFのテキストを読み取る |
| Detect | PII検出（表示ページ / 全ページ） |
| 対象削除 | 検出結果を削除（表示ページ / 全ページ） |
| 重複削除 | 重複する検出結果を整理（表示ページ / 全ページ） |
| 保存 | PDFとサイドカーJSONマッピングを保存 |
| エクスポート | 各形式でエクスポート |
| ヘルプ | 重複削除優先順位の説明 |

#### エクスポート形式
- アノテーション付きPDF
- マスクPDF
- マスク（画像として保存）
- マーク（画像として保存）
- 検出結果一覧（CSV）

#### 検出結果テーブル
- **検出元ラベル**: 各エンティティに「手動 / 追加 / 自動」の検出元を表示
- **正規表現フィルター**: ページ・種別・テキスト・位置・検出元の各列を正規表現でフィルタリング
- **ソート**: 列ヘッダークリックでソート
- **選択語の登録**: 選択した検出語をワンクリックで「無視対象」または「追加検出対象」に登録

#### 重複排除の優先順位
同一テキストが複数の検出元で見つかった場合の優先順位：

> **検出元 (origin)** > **包含 (contain)** > **長さ (length)**

- **検出元の優先順位**: 手動 > 追加 = 自動
- 追加検出と自動検出が重複した場合は追加検出を優先して自動を除去

#### キーボードショートカット
| キー | 動作 |
|------|------|
| `PgDown` | 次のページへ |
| `PgUp` | 前のページへ |
| `Home` | 最初のページへ |
| `End` | 最後のページへ |
| `Delete` | 選択エンティティを削除 |
| `Backspace` | 選択エンティティを無視対象に登録 |
| `Insert` | 選択エンティティを追加検出対象に登録 |
| `Ctrl+A` | 表示ページの全エンティティを選択 |

#### 設定ダイアログ（リアルタイム自動保存）
- **spaCyモデル選択**: インストール済みモデルから選択
- **重複削除設定**:
  - 対象重複判定: 同じ対象のみ / 異なる対象でも同一扱い
  - 重複判定: 包含関係のみ / 一部重なりも含む
- **テキスト前処理設定**:
  - 改行無視（デフォルトON）: ブロック・ページ境界の改行を無視して検出
  - 空白無視（デフォルトOFF）: 空白文字を除去して検出
- **チャンク分割設定**: 長い文書をチャンクに分割して処理
- 設定変更はリアルタイムで `$HOME/.presidio/config.json` に自動保存
- ファイルダイアログの最終使用ディレクトリを記憶

## Optional dependencies

| Extra名 | 内容 |
|---|---|
| `dev` | pytest / black / mypy など開発ツール |
| `gpu` | 大規模日本語モデル・GPU関連 |
| `minimal` | 最小構成 |
| `gui` | PyQt6 GUI関連 |
| `ocr` | NDLOCR-Lite OCR関連 |
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
