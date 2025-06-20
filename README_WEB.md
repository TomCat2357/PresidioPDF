# PDF個人情報マスキングツール - Webアプリケーション版

## 概要

デスクトップGUI版 (`presidio_gui_minimal.py`) をWebアプリケーションに変換したものです。ブラウザで動作し、同等の機能を提供します。

## 主な機能

- **PDFファイルアップロード**: ドラッグ&ドロップまたはクリックでファイル選択
- **個人情報検出**: Presidioを使用した日本語対応の個人情報検出
- **PDFビューア**: ページナビゲーション、ズーム機能
- **検出結果表示**: エンティティ一覧表示と詳細情報
- **エンティティ管理**: 検出結果の削除、編集
- **PDFマスキング**: 検出結果をPDFに注釈として適用
- **設定管理**: 検出対象エンティティ、信頼度閾値の設定

## システム要件

- **Python 3.11+**
- **uv パッケージマネージャー**
- **日本語spaCyモデル** または **GINZA**
- **モダンWebブラウザ** (Chrome, Firefox, Safari, Edge)

## セットアップ手順

### 1. 仮想環境の準備

```bash
# 仮想環境を作成・有効化（uvを使用）
uv venv .venv
source .venv\bin\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
```

### 2. 依存関係のインストール

```bash
# Web版の依存関係をインストール
uv pip install -r requirements_web.txt

# 日本語spaCyモデルをインストール
uv pip install https://github.com/explosion/spacy-models/releases/download/ja_core_news_sm-3.7.0/ja_core_news_sm-3.7.0-py3-none-any.whl
uv pip install https://github.com/explosion/spacy-models/releases/download/ja_core_news_md-3.7.0/ja_core_news_md-3.7.0-py3-none-any.whl

# または、GINZA（高精度日本語モデル）をインストール
uv run python -m pip install 'ginza[ja]'
```

### 3. 設定ファイルの確認

元のプロジェクトの設定ファイルを使用します：

```bash
# 設定ファイルが存在することを確認
ls config/low_threshold.yaml
```

### 4. Webアプリケーションの起動

```bash
# 開発サーバーを起動
uv run python presidio_web_app.py

# または、本番環境用（Gunicornなど）
uv run gunicorn -w 4 -b 0.0.0.0:5000 presidio_web_app:app
```

### 5. ブラウザでアクセス

```
http://localhost:5000
```

## 使用方法

### 1. PDFファイルのアップロード

- 左側パネルの「PDFファイル選択」エリアをクリック
- または、PDFファイルをドラッグ&ドロップ
- ファイルが正常にアップロードされると、右側にPDFが表示されます

### 2. 個人情報の検出

- 「検出開始」ボタンをクリック
- 検出結果が左側パネルの「検出結果」に表示されます
- 各結果をクリックすると詳細情報が表示され、該当ページに移動します

### 3. 検出結果の管理

- **エンティティ詳細**: 選択したエンティティの詳細情報を表示
- **削除**: 不要な検出結果を削除
- **PDFに適用**: 現在の検出結果をPDFファイルに注釈として適用

### 4. 設定の調整

- 「設定」ボタンをクリックして設定画面を開く
- **検出対象エンティティ**: 人名、場所、電話番号、日時から選択
- **信頼度閾値**: 検出結果の信頼度の最小値を設定

### 5. PDFビューア操作

- **ページナビゲーション**: 前ページ/次ページボタン
- **ズーム**: スライダーで拡大率を調整（25%〜200%）

## アーキテクチャ

### バックエンド (Flask)

- **`presidio_web_app.py`**: メインのFlaskアプリケーション
- **`PresidioPDFWebApp`クラス**: セッション管理とPDF処理
- **API エンドポイント**: RESTful API for フロントエンド通信

### フロントエンド

- **`templates/index.html`**: メインのHTMLテンプレート
- **`static/js/app.js`**: JavaScript アプリケーションロジック
- **Bootstrap 5**: レスポンシブなUI
- **Font Awesome**: アイコン

### セッション管理

- Flask session を使用したユーザーセッション管理
- アップロードされたファイルは `web_uploads/` ディレクトリに保存
- セッションごとに独立したPDF処理インスタンス

## API エンドポイント

- `POST /api/upload`: PDFファイルアップロード
- `POST /api/detect`: 個人情報検出実行
- `GET /api/page/<page_num>`: PDF ページ画像取得
- `DELETE /api/delete_entity/<index>`: エンティティ削除
- `POST /api/apply_pdf`: PDF に変更適用
- `GET/POST /api/settings`: 設定の取得・更新

## セキュリティ考慮事項

- **ファイルサイズ制限**: 最大50MB
- **ファイル形式制限**: PDFファイルのみ
- **セキュアファイル名**: アップロードファイル名のサニタイズ
- **セッション分離**: ユーザーごとのデータ分離

## トラブルシューティング

### よくある問題

1. **spaCyモデルが見つからない**
   ```bash
   uv run python -m spacy download ja_core_news_sm
   ```

2. **ポート5000が使用中**
   ```bash
   # 別のポートを使用
   uv run python presidio_web_app.py --port 8080
   ```

3. **メモリ不足**
   - 大きなPDFファイルの場合、より多くのメモリが必要
   - ページ単位での処理に最適化済み

### ログファイル

- **`presidio_web_YYYYMMDD_HHMMSS.log`**: アプリケーションログ
- ブラウザの開発者ツール（F12）でクライアント側エラーを確認

## デスクトップ版との違い

| 機能 | デスクトップ版 | Web版 |
|------|-------------|-------|
| インターフェース | FreeSimpleGUI | HTML/CSS/JavaScript |
| ファイルアクセス | ローカル直接 | アップロード経由 |
| PDF表示 | PyMuPDF直接 | Base64画像変換 |
| 設定保存 | ローカル | セッション内 |
| マルチユーザー | 単一 | 対応 |

## 今後の拡張予定

- [ ] ユーザー認証機能
- [ ] ファイル履歴管理
- [ ] バッチ処理機能
- [ ] 設定のエクスポート/インポート
- [ ] PDF.js による高度なPDF表示
- [ ] WebSocket によるリアルタイム進捗表示

## ライセンス

元のプロジェクトと同じライセンスに従います。