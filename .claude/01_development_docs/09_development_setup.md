# 開発環境セットアップ

## 概要
PresidioPDFプロジェクトの開発環境構築手順を定義する。新規開発者（人間・AI）が迅速に開発を開始できるよう、詳細な手順とトラブルシューティング情報を提供する。

## 必要システム要件

### ハードウェア要件
```yaml
minimum_requirements:
  cpu: "x64 compatible processor"
  memory: "4GB RAM"
  disk: "2GB free space"
  
recommended_requirements:
  cpu: "Multi-core x64 processor"
  memory: "8GB+ RAM"
  disk: "5GB+ free space (SSD推奨)"
  gpu: "NVIDIA GPU (CUDA対応) - optional for trf model"
```

### ソフトウェア要件
- **Python**: 3.8+ (3.9-3.11推奨)
- **uv**: 最新版（パッケージ管理）
- **Git**: 2.20+
- **エディタ**: VS Code推奨（拡張設定含む）

## 環境構築手順

### 1. リポジトリのクローン
```bash
# リポジトリクローン
git clone https://github.com/your-org/PresidioPDF.git
cd PresidioPDF

# 開発ブランチ作成（オプション）
git checkout -b feature/your-feature-name
```

### 2. Python環境確認
```bash
# Pythonバージョン確認
python --version  # 3.8+ であること

# uvインストール確認
uv --version

# uvがない場合のインストール
# Linux/macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell):
irm https://astral.sh/uv/install.ps1 | iex
```

### 3. 依存関係のインストール
```bash
# 基本依存関係インストール
uv sync

# 開発者向けフル依存関係
uv sync --extra dev --extra gpu

# 各種オプション依存関係
uv sync --extra web     # Web UI開発
uv sync --extra gui     # デスクトップGUI開発
uv sync --extra gpu     # GPU最適化モデル
```

### 4. spaCy日本語モデルのダウンロード
```bash
# 基本モデル（開発用、必須）
uv run python -m spacy download ja_core_news_sm

# 高精度モデル（オプション）
uv run python -m spacy download ja_core_news_md
uv run python -m spacy download ja_core_news_lg

# Transformerモデル（GPU推奨）
uv run python -m spacy download ja_core_news_trf
```

### 5. 設定ファイルの準備
```bash
# 設定ファイルのコピー
cp config/config_template.yaml config/config.yaml

# 開発用設定の調整（必要に応じて）
# config.yamlでspaCyモデルやパス設定を調整
```

## IDE設定（VS Code推奨）

### 必須拡張機能
```json
// .vscode/extensions.json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance", 
    "ms-python.mypy-type-checker",
    "ms-python.black-formatter",
    "ms-python.isort",
    "charliermarsh.ruff",
    "ms-vscode.test-adapter-converter",
    "ms-python.pytest"
  ]
}
```

### VS Code設定
```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.mypyEnabled": true,
  "python.linting.mypyArgs": ["--strict", "--ignore-missing-imports"],
  "python.formatting.provider": "black",
  "python.formatting.blackArgs": ["--line-length", "100"],
  "python.sortImports.args": ["--profile", "black"],
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests/"],
  "files.exclude": {
    "**/__pycache__": true,
    "**/.pytest_cache": true,
    "**/.mypy_cache": true,
    ".venv/": true
  },
  "python.analysis.typeCheckingMode": "strict",
  "python.analysis.autoImportCompletions": true
}
```

### デバッグ設定
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "CLI Debug",
      "type": "python",
      "request": "launch",
      "module": "src.cli",
      "args": ["test_pdfs/sample.pdf", "--verbose"],
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    },
    {
      "name": "Web App Debug",
      "type": "python", 
      "request": "launch",
      "program": "${workspaceFolder}/src/web_main.py",
      "args": ["--debug", "--port", "5000"],
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}"
    },
    {
      "name": "Test Debug",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/", "-v", "-s"],
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

## 開発ワークフロー

### コード品質チェック
```bash
# フォーマット適用
uv run black .
uv run isort .

# リンティング
uv run ruff check .
uv run mypy src/

# 型チェック（厳密）
uv run mypy src/ --strict

# 全チェック実行（推奨）
uv run python scripts/quality_check.py
```

### テスト実行
```bash
# 基本テスト実行
uv run pytest

# 詳細出力
uv run pytest -v -s

# カバレッジ付き実行
uv run pytest --cov=src --cov-report=html

# 特定ファイルのテスト
uv run pytest tests/test_analyzer.py

# マークを指定したテスト実行
uv run pytest -m "not slow"  # 時間のかかるテストを除外
```

### 開発サーバー起動
```bash
# Web UI開発サーバー
uv run python src/web_main.py --debug --port 5000

# バックグラウンド実行
nohup uv run python src/web_main.py --port 5000 > web.log 2>&1 &

# CLI動作確認
uv run python -m src.cli test_pdfs/sample.pdf --verbose
```

## 環境変数設定

### 開発用環境変数
```bash
# .env ファイル（開発用）
export PRESIDIO_DEBUG=true
export PRESIDIO_LOG_LEVEL=DEBUG
export PRESIDIO_MODEL_CACHE_DIR=data/models/
export PRESIDIO_OUTPUT_DIR=outputs/
export PRESIDIO_WEB_PORT=5000
export PRESIDIO_WEB_HOST=localhost

# Flask開発設定
export FLASK_ENV=development
export FLASK_DEBUG=1

# テスト用設定
export PRESIDIO_TEST_MODE=true
export PRESIDIO_TEST_DATA_DIR=tests/fixtures/
```

### 本番環境変数
```bash
# .env.production
export PRESIDIO_DEBUG=false
export PRESIDIO_LOG_LEVEL=INFO
export PRESIDIO_MODEL_CACHE_DIR=/app/models/
export PRESIDIO_OUTPUT_DIR=/app/outputs/
export PRESIDIO_WEB_PORT=8080
export PRESIDIO_WEB_HOST=0.0.0.0

# セキュリティ設定
export PRESIDIO_SECRET_KEY=your-secret-key
export PRESIDIO_MAX_FILE_SIZE=52428800  # 50MB
export PRESIDIO_SESSION_TIMEOUT=3600    # 1時間
```

## データベース・ファイルセットアップ

### 必要ディレクトリ作成
```bash
# 開発用ディレクトリ構造作成
mkdir -p {data/models,outputs/processed,outputs/reports,outputs/backups,web_uploads,logs}

# 権限設定（Linux/macOS）
chmod 755 outputs/ web_uploads/ logs/
chmod 644 config/config.yaml
```

### テストデータ準備
```bash
# テスト用PDFファイルの配置
mkdir -p test_pdfs/
# サンプルファイルをtest_pdfs/に配置

# テストデータ生成スクリプト実行
uv run python scripts/generate_test_data.py
```

## トラブルシューティング

### よくある問題と解決方法

#### 1. spaCyモデルのダウンロードエラー
```bash
# エラー: Can't find model 'ja_core_news_sm'
# 解決法:
uv run python -m spacy download ja_core_news_sm

# 手動ダウンロードが必要な場合
wget https://github.com/explosion/spacy-models/releases/download/ja_core_news_sm-3.7.0/ja_core_news_sm-3.7.0-py3-none-any.whl
uv pip install ja_core_news_sm-3.7.0-py3-none-any.whl
```

#### 2. メモリ不足エラー
```bash
# 大きなモデル使用時のメモリ不足対策
# config.yamlでバッチサイズを調整:
nlp:
  batch_size: 16  # デフォルト32から減らす
  spacy_model: "ja_core_news_sm"  # より軽量なモデル使用
```

#### 3. パーミッションエラー
```bash
# Linux/macOSでの権限問題
sudo chown -R $USER:$USER .venv/
chmod -R 755 outputs/ web_uploads/

# Windowsでの実行ポリシー問題
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 4. ポート使用中エラー
```bash
# ポート5000が使用中の場合
lsof -ti:5000 | xargs kill -9  # Linux/macOS
netstat -ano | findstr :5000   # Windows

# 別ポートで起動
uv run python src/web_main.py --port 5001
```

## 開発ツール・スクリプト

### 便利スクリプト作成
```python
# scripts/dev_helpers.py
import subprocess
import sys
from pathlib import Path

def run_quality_checks():
    """コード品質チェック実行"""
    commands = [
        ["uv", "run", "black", "."],
        ["uv", "run", "isort", "."],
        ["uv", "run", "mypy", "src/"],
        ["uv", "run", "pytest", "--cov=src"]
    ]
    
    for cmd in commands:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error in {cmd[2]}: {result.stderr}")
            return False
    return True

def setup_dev_environment():
    """開発環境セットアップ"""
    # 必要ディレクトリ作成
    dirs = ["data/models", "outputs/processed", "outputs/reports", 
            "outputs/backups", "web_uploads", "logs"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    
    # spaCyモデルダウンロード
    subprocess.run(["uv", "run", "python", "-m", "spacy", "download", "ja_core_news_sm"])
    
    print("Development environment setup complete!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "quality":
            run_quality_checks()
        elif sys.argv[1] == "setup":
            setup_dev_environment()
```

### Makefileの提供
```makefile
# Makefile
.PHONY: install test lint format clean dev

install:
	uv sync --extra dev

test:
	uv run pytest --cov=src --cov-report=html

lint:
	uv run mypy src/
	uv run ruff check .

format:
	uv run black .
	uv run isort .

quality: format lint test

clean:
	rm -rf .mypy_cache/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf **/__pycache__/
	rm -rf build/ dist/ *.egg-info/

dev:
	uv run python src/web_main.py --debug --port 5000

cli:
	uv run python -m src.cli test_pdfs/sample.pdf --verbose

setup-models:
	uv run python -m spacy download ja_core_news_sm
	uv run python -m spacy download ja_core_news_md
```

## CI/CD環境での開発

### GitHub Actions設定参考
```yaml
# .github/workflows/dev.yml
name: Development Checks
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, 3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v3
    - name: Install uv
      uses: astral-sh/setup-uv@v1
    - name: Set up Python ${{ matrix.python-version }}
      run: uv python install ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        uv sync --extra dev
        uv run python -m spacy download ja_core_news_sm
    - name: Run quality checks
      run: |
        uv run black --check .
        uv run mypy src/
        uv run pytest --cov=src
```