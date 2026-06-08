# 依存関係戦略

> **【更新: 2026-06】** Python 3.14 移行に伴い、NLP は spaCy/Presidio から **SudachiPy** へ、
> OCR は NDLOCR-Lite から **RapidOCR v3** へ全面置換。`requires-python = ">=3.14,<3.15"`。
> 正規の定義は `pyproject.toml` を参照。

## パッケージ管理方針
- **メインツール**: `uv` - 高速で信頼性の高いPythonパッケージ管理
- **pip使用禁止**: このプロジェクトでは`uv`のみを使用

## コア依存（必須）
- `click` — CLI
- `sudachipy` + `sudachidict-core` — 形態素解析ベースの PII 検出
- `PyMuPDF` — PDF 処理（cp310-abi3 wheel）
- `PyYAML` — 設定
- `phonenumbers` — 電話番号の妥当性検証

## オプション依存関係（extras）
- **dev**: pytest / black / flake8 / mypy など開発ツール
- **gui**: PyQt6 デスクトップ GUI
- **ocr**: RapidOCR v3（onnxruntime / opencv / numpy / shapely / pyclipper / Pillow を含む）

## 依存関係管理コマンド
```bash
# 基本インストール（SudachiPy ベースのコア検出）
uv sync

# 拡張インストール
uv sync --extra gui    # PyQt GUI
uv sync --extra ocr    # RapidOCR OCR
uv sync --extra dev    # 開発ツール

# 依存関係追加
uv add package-name           # 本番依存関係
uv add --dev pytest-mock     # 開発依存関係
```

## SudachiPy 辞書 / 分割モード戦略
辞書種別と分割モードで精度・被覆を調整：
- 辞書: `core`（デフォルト）/ `full`（固有名詞被覆を上げる・数百MB）/ `small`
- 分割モード: `A`（短）/ `B`（中）/ `C`（長単位・固有名詞検出に推奨）
- 固有名詞サブ品詞（人名→PERSON / 地名→LOCATION / その他固有名詞→PROPER_NOUN）で NER 相当を辞書のみで実現

## OCR モデル戦略（RapidOCR v3）
- **軽量(mobile)**: 既定。高速・小モデル
- **高精度(server)**: 大モデル・高精度（検出器を server 化）
- 日本語認識は PP-OCRv4（`LangRec.JAPAN`）、検出は PP-OCRv5。モデルは初回実行時に自動DL