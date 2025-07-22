# 依存関係戦略

## パッケージ管理方針
- **メインツール**: `uv` - 高速で信頼性の高いPythonパッケージ管理
- **pip使用禁止**: このプロジェクトでは`uv`のみを使用

## オプション依存関係
プロジェクトでは用途別のオプション依存関係を提供：

### 基本構成
- **Default (CPU)**: 基本機能・CPUのみモデル
- **Minimal**: 軽量インストール・基本PDF処理

### 拡張構成
- **GPU**: GPU最適化モデル（高性能）
- **Web**: Webアプリケーション依存関係
- **GUI**: デスクトップGUI依存関係
- **Dev**: 開発・テストツール

## 依存関係管理コマンド
```bash
# 基本インストール
uv sync

# 拡張インストール
uv sync --extra gpu    # GPU サポート
uv sync --extra web    # Web アプリケーション
uv sync --extra dev    # 開発ツール

# 依存関係追加
uv add package-name           # 本番依存関係
uv add --dev pytest-mock     # 開発依存関係
```

## spaCy日本語モデル戦略
複数の日本語モデルをサポートし、精度とパフォーマンスのバランスを調整：
- `ja-core-news-sm`: 軽量（デフォルト）
- `ja-core-news-md`: 中精度
- `ja-core-news-lg`: 高精度（GPU推奨）
- `ja-core-news-trf`: 最高精度（Transformer、GPU必須）