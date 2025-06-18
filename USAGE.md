# PDF個人情報検出・マスキングシステム 使用方法ガイド

## 概要

PDF個人情報検出・マスキングシステムは、PDFファイルから日本の個人情報を自動検出し、注釈またはハイライトでマスキングするツールです。高性能なPyMuPDFライブラリとMicrosoft Presidioを使用して、正確な個人情報検出とPDF処理を実現します。

## 主な機能

### PDF処理（PyMuPDF版）
- **高性能マスキング**: PyMuPDFによる注釈・ハイライト・両方の組み合わせ
- **バッチ処理**: フォルダ内の複数ファイル一括処理
- **除外機能**: 処理済みファイルの自動スキップ
- **詳細レポート**: JSON/CSV形式でのレポート生成

### 主要な検出機能
- **日本語特化検出**: マイナンバー、年号、電話番号、人名等に対応
- **カスタム認識器**: ユーザー定義の検出パターン
- **設定管理**: YAML設定ファイルによる詳細制御
- **柔軟な閾値設定**: エンティティ別の信頼度調整

## システム要件

- **Python**: 3.11以上
- **OS**: Windows、Linux、macOS
- **spaCyモデル**: 日本語NLPモデル (`ja_core_news_trf`、`ja_core_news_sm`、または `ja_ginza`/`ja_ginza_electra`)

## インストールと初期設定

### 1. 仮想環境のセットアップ

```bash
# 仮想環境をアクティベート
source .venv/bin/activate

# 依存関係をインストール
uv sync

# 日本語spaCyモデルをインストール
uv run python -m spacy download ja_core_news_sm
# または高精度モデル（推奨）
uv run python -m spacy download ja_core_news_trf

# GINZA（高精度日本語処理モデル）をインストール
uv run python -m pip install 'ginza[ja]'
```

### 2. 設定ファイルの準備

システムには複数の事前設定されたYAMLファイルが用意されています：

```bash
# 基本的なハイライト処理
cp config/highlighting_only.yaml config.yaml      # ハイライトのみでマスキング

# 検出精度を重視した設定
cp config/high_threshold.yaml config.yaml         # 高閾値で誤検出を最小化

# 特定の個人情報のみ検出
cp config/specific_entities.yaml config.yaml      # 電話番号・マイナンバーのみ

# 既存PDFの注釈読み取り
cp config/read_mode.yaml config.yaml              # 注釈・ハイライト読み取り専用

# 包括的テスト用
cp config/comprehensive_test.yaml config.yaml     # 全機能を有効化

# より多くの候補を検出
cp config/low_threshold.yaml config.yaml          # 低閾値で広範囲検出
```

## 基本的な使用方法

### PDF処理

#### 単一ファイルの処理

```bash
# 基本的な処理
uv run python src/pdf_presidio_processor.py document.pdf

# 詳細ログ付き
uv run python src/pdf_presidio_processor.py document.pdf --verbose

# カスタム設定ファイル使用
uv run python src/pdf_presidio_processor.py document.pdf --config config/basic.yaml
```

#### フォルダ一括処理

```bash
# フォルダ内の全PDFファイルを処理
uv run python src/pdf_presidio_processor.py test_pdfs/

# 詳細ログ付き
uv run python src/pdf_presidio_processor.py test_pdfs/ --verbose
```

## 設定ファイル（config.yaml）の詳細

### 基本設定

```yaml
# 検出対象の個人情報エンティティ
enabled_entities:
  PHONE_NUMBER: true      # 電話番号
  PERSON: true           # 人名
  LOCATION: true         # 場所・住所
  DATE_TIME: false       # 日時
  INDIVIDUAL_NUMBER: true # マイナンバー
  YEAR: true             # 年号
  PROPER_NOUN: false     # 固有名詞

# 信頼度の閾値設定
thresholds:
  default: 0.5           # デフォルト閾値
  PHONE_NUMBER: 0.7      # 電話番号の閾値
  PERSON: 0.6            # 人名の閾値
  INDIVIDUAL_NUMBER: 0.8 # マイナンバーの閾値
```

### PDF処理設定

```yaml
pdf_processing:
  masking:
    method: "highlight"          # マスキング方式: annotation（ボックス）, highlight（ハイライト）, both（両方）
    text_display_mode: "verbose" # 文字表示モード: silent（文字なし）, minimal（最小限）, verbose（詳細）
    annotation_settings:
      include_text: false        # 注釈にテキストを含めるか（verboseモード時のみ有効）
      font_size: 12
  
  output_suffix: "_masked" # 出力ファイルのサフィックス
  backup_enabled: false    # バックアップ作成（サフィックス付きなので通常は不要）
  
  # レポート設定
  report:
    generate_report: true  # レポート生成
    format: "json"        # レポート形式: json, csv
    include_detected_text: false
```

#### 文字表示設定の優先関係

**最優先**: `text_display_mode`（文字表示モード）
**補助設定**: `annotation_settings.include_text`

| モード | 表示内容 | `include_text`の影響 | 例 |
|--------|----------|---------------------|-----|
| `silent` | 文字なし（色のみ） | **無視** | 色付き矩形のみ |
| `minimal` | エンティティタイプのみ | **無視** | 「人名」「電話番号」 |
| `verbose` | 詳細情報 | **有効** | 「【個人情報】人名 (信頼度: 85%)」 |

**`include_text: true`の効果（verboseモード時のみ）**:
```
【個人情報】人名 (信頼度: 85.0%)
テキスト: 田中太郎...
```

### 重複除去設定

```yaml
deduplication:
  enabled: true                # 重複除去を有効化
  method: "overlap"            # 重複判定方法: overlap（重複判定）, exact（完全一致）, contain（包含関係）
  overlap_mode: "partial_overlap"  # 重複の範囲: contain_only（包含のみ）, partial_overlap（一部重なりも含む）
  priority: "score"            # 優先順位: score（スコア優先）, wider_range（広い範囲優先）, narrower_range（狭い範囲優先）, entity_type（エンティティタイプ優先）
  entity_priority_order:       # エンティティタイプ優先時の順序（重要度の高い順）
    - "INDIVIDUAL_NUMBER"
    - "PHONE_NUMBER"
    - "PERSON"
    - "LOCATION"
    - "DATE_TIME"
    - "YEAR"
    - "PROPER_NOUN"
```

**重複判定モードの説明:**
- **contain_only**: どちらかがどちらかを完全に包含する場合のみ重複と判定
- **partial_overlap**: 少しでも重なりがある場合に重複と判定（デフォルト）

### カスタム人名辞書

```yaml
custom_names:
  enabled: true           # カスタム人名辞書を有効化
  use_with_auto_detection: true # 自動検出と併用
  name_list:             # 固定の人名リスト
    - "田中太郎"
    - "佐藤花子"
    - "山田次郎"
  name_patterns:         # 人名パターン
    - name: "役職付き人名"
      regex: "(部長|課長|主任)\\s*([\\u4e00-\\u9fff]{2,4})"
      score: 0.8
```

### 除外設定

```yaml
exclusions:
  text_exclusions:       # 共通除外ワード
    - "例："
    - "サンプル"
    - "テスト"
  entity_exclusions:     # エンティティ別除外
    PERSON:
      - "システム"
      - "管理者"
    PHONE_NUMBER:
      - "0000-00-0000"
```

## コマンドライン オプション

### PDF処理のオプション

```bash
# ヘルプ表示
uv run python src/pdf_presidio_processor.py --help

# 基本設定オプション
--config, -c          # 設定ファイルのパス
--verbose, -v         # 詳細ログ表示
--output-dir, -o      # 出力ディレクトリ

# モード選択オプション
--read-mode, -r       # 読み取りモード

# マスキング設定オプション
--masking-method      # マスキング方式 (annotation/highlight/both)
--masking-text-mode   # マスキング文字表示モード (silent/minimal/verbose)

# 処理設定オプション
--spacy-model, -m     # 使用するspaCyモデル名
--deduplication-mode         # 重複除去モード
--deduplication-overlap-mode  # 重複判定モード

# 例：カスタム設定ファイル使用
uv run python src/pdf_presidio_processor.py document.pdf --config config/highlighting_only.yaml

# 例：詳細ログ表示
uv run python src/pdf_presidio_processor.py document.pdf --verbose

# 例：重複除去モード指定
uv run python src/pdf_presidio_processor.py document.pdf --deduplication-mode score

# 例：spaCyモデル指定
uv run python src/pdf_presidio_processor.py document.pdf --spacy-model ja_core_news_trf

# 例：GINZA使用（高精度日本語処理）
uv run python src/pdf_presidio_processor.py document.pdf --spacy-model ja_ginza

# 例：GINZA Electra使用（最高精度、処理時間長め）
uv run python src/pdf_presidio_processor.py document.pdf --spacy-model ja_ginza_electra

# 例：マスキング方式と文字表示モードの指定
uv run python src/pdf_presidio_processor.py document.pdf --masking-method annotation --masking-text-mode verbose
uv run python src/pdf_presidio_processor.py document.pdf --masking-method highlight --masking-text-mode minimal  
uv run python src/pdf_presidio_processor.py document.pdf --masking-method both --masking-text-mode silent
```

### 新しいコマンドライン引数サポート

ConfigManagerの更新により、色設定以外のほぼ全ての設定項目をコマンドライン引数で指定可能になりました。

#### エンティティと閾値の設定

```bash
# 特定のエンティティのみ検出
uv run python src/pdf_presidio_processor.py document.pdf --entities PERSON PHONE_NUMBER

# 単一の閾値設定
uv run python src/pdf_presidio_processor.py document.pdf --threshold 0.8

# エンティティ別閾値設定（JSON形式）
uv run python src/pdf_presidio_processor.py document.pdf --thresholds '{"PERSON": 0.7, "PHONE_NUMBER": 0.9}'
```

#### カスタム人名辞書の設定

```bash
# カスタム人名設定（JSON形式）
uv run python src/pdf_presidio_processor.py document.pdf --custom_names '{
  "enabled": true,
  "name_list": ["田中太郎", "佐藤花子"],
  "use_with_auto_detection": true
}'
```

#### 除外設定

```bash
# 除外設定（JSON形式）
uv run python src/pdf_presidio_processor.py document.pdf --exclusions '{
  "text_exclusions": ["サンプル", "テスト"],
  "entity_exclusions": {
    "PERSON": ["システム", "管理者"]
  }
}'
```

#### PDF処理固有の設定

```bash
# PDFマスキング方式の指定
uv run python src/pdf_presidio_processor.py document.pdf --masking-method annotation

# PDFマスキング文字表示モードの指定  
uv run python src/pdf_presidio_processor.py document.pdf --masking-text-mode silent

# マスキング方式と文字表示モードの組み合わせ
uv run python src/pdf_presidio_processor.py document.pdf --masking-method both --masking-text-mode minimal

# PDF出力サフィックスの指定
uv run python src/pdf_presidio_processor.py document.pdf --pdf_output_suffix "_secured"

# PDFバックアップの有効/無効
uv run python src/pdf_presidio_processor.py document.pdf --pdf_backup true
```

#### その他の設定

```bash
# 出力ファイルサフィックス
uv run python src/pdf_presidio_processor.py document.pdf --suffix "_processed"

# バックアップ作成
uv run python src/pdf_presidio_processor.py document.pdf --backup true

# レポート生成
uv run python src/pdf_presidio_processor.py document.pdf --report true

# バッチサイズの調整
uv run python src/pdf_presidio_processor.py folder/ --batch_size 25

# 再帰検索の有効/無効
uv run python src/pdf_presidio_processor.py folder/ --recursive false
```

#### 複合的な使用例

```bash
# 高セキュリティ設定での処理（重複除去付き）
uv run python src/pdf_presidio_processor.py document.pdf \
  --entities PERSON PHONE_NUMBER INDIVIDUAL_NUMBER \
  --thresholds '{"PERSON": 0.9, "PHONE_NUMBER": 0.95, "INDIVIDUAL_NUMBER": 0.99}' \
  --masking-method annotation \
  --masking-text-mode minimal \
  --deduplication-mode entity_type \
  --deduplication-overlap-mode contain_only \
  --backup true \
  --report true \
  --verbose

# カスタム除外設定付きの処理（スコア優先重複除去）
uv run python src/pdf_presidio_processor.py folder/ \
  --exclusions '{"text_exclusions": ["サンプル", "テスト", "例"], "entity_exclusions": {"PERSON": ["システム"]}}' \
  --pdf_output_suffix "_secured" \
  --deduplication-mode score \
  --deduplication-overlap-mode partial_overlap \
  --batch_size 10

# 包含関係のみで重複除去（より精密な除去）
uv run python src/pdf_presidio_processor.py document.pdf \
  --deduplication-mode wider_range \
  --deduplication-overlap-mode contain_only \
  --verbose

# 一部重なりも含む幅広い重複除去（デフォルト動作）
uv run python src/pdf_presidio_processor.py document.pdf \
  --deduplication-mode score \
  --deduplication-overlap-mode partial_overlap

# 重複除去比較テスト
uv run python src/pdf_presidio_processor.py document.pdf --config config/deduplication_score.yaml
uv run python src/pdf_presidio_processor.py document.pdf --config config/deduplication_wider.yaml  
uv run python src/pdf_presidio_processor.py document.pdf --config config/deduplication_entity.yaml
```

**注意事項:**
- 色設定（colors）はYAMLファイルでのみ設定可能です
- JSON形式の引数は適切にクォートで囲む必要があります
- コマンドライン引数はYAML設定ファイルより優先されます

#### PDF注釈読み取りモード

```bash
# 読み取りモード: 既存の注釈・ハイライトを読み取り
uv run python src/pdf_presidio_processor.py document.pdf --read-mode

# 詳細表示付きの読み取り
uv run python src/pdf_presidio_processor.py document.pdf --read-mode --verbose

# レポート生成なしで読み取り
uv run python src/pdf_presidio_processor.py document.pdf --read-mode --no-read-report

# フォルダ内の全PDFファイルを読み取り
uv run python src/pdf_presidio_processor.py test_pdfs/ --read-mode --verbose
```

**読み取り可能な情報:**
- **場所**: 座標（x0, y0, x1, y1）、ページ番号、幅・高さ
- **テキスト位置**: 行番号、文字位置、行内容 ⭐ NEW
- **文字列**: 注釈がカバーしているテキスト内容
- **色**: RGB値とHex色コード（線色・塗り色）
- **透明度**: 0.0〜1.0の透明度値
- **メタデータ**: 作成日時、タイトル、内容、作成者等

**読み取りレポート例（JSON形式）:**
```json
{
  "pdf_file": "document.pdf",
  "total_annotations": 15,
  "annotations_by_type": {"Highlight": 8, "FreeText": 7},
  "annotations_by_page": {"1": 5, "2": 10},
  "annotations": [
    {
      "annotation_type": "Highlight",
      "coordinates": {"page_number": 1, "x0": 100.5, "y0": 200.3, "x1": 180.2, "y1": 215.8},
      "text_position": {
        "line_number": 15,
        "char_start_in_line": 8,
        "char_end_in_line": 12,
        "line_content": "申請者: 田中太郎 (東京都渋谷区在住)",
        "total_lines_on_page": 45
      },
      "covered_text": "田中太郎",
      "color_info": {"stroke_color": {"rgb": [1.0, 0.0, 0.0], "hex": "#ff0000"}},
      "opacity": 0.5,
      "creation_date": "D:20241215143052+09'00'"
    }
  ]
}
```

**テキスト位置情報の説明:**
- `line_number`: ページ内の行番号（1から開始）
- `char_start_in_line`: 行内の開始文字位置（0から開始）
- `char_end_in_line`: 行内の終了文字位置
- `line_content`: その行の全体テキスト内容
- `total_lines_on_page`: ページ内の総行数

## 検出される個人情報の種類

| エンティティタイプ | 説明 | 例 |
|-------------------|------|-----|
| `PERSON` | 人名 | 田中太郎、佐藤さん |
| `PHONE_NUMBER` | 電話番号 | 03-1234-5678、090-1234-5678 |
| `LOCATION` | 場所・住所 | 東京都渋谷区、大阪市北区 |
| `DATE_TIME` | 日時 | 2024年1月1日、令和6年 |
| `INDIVIDUAL_NUMBER` | マイナンバー | 12桁の数字 |
| `YEAR` | 年号 | 令和6年、平成30年 |
| `PROPER_NOUN` | 固有名詞 | 会社名、製品名など |

## 出力ファイルとレポート

### 出力ファイル

- **PDF処理**: `document_masked.pdf`（注釈・ハイライト付き）
  - デフォルト設定により `_masked` サフィックス
- **バックアップ**: `document_backup.pdf`（設定により作成される元ファイルの複製）
- **レポート**: `pdf_report_YYYYMMDD_HHMMSS.json`（設定により生成される処理結果の詳細）

### レポート例（JSON形式）

```json
{
  "processing_stats": {
    "files_processed": 1,
    "total_entities_found": 15,
    "entities_by_type": {
      "PERSON": 5,
      "PHONE_NUMBER": 3,
      "LOCATION": 7
    }
  },
  "file_results": [
    {
      "input_file": "document.pdf",
      "output_file": "document_masked.pdf",
      "total_entities_found": 15,
      "entities_by_type": {
        "PERSON": 5,
        "PHONE_NUMBER": 3,
        "LOCATION": 7
      }
    }
  ]
}
```

## トラブルシューティング

### よくある問題と解決方法

#### 1. spaCyモデルが見つからない

```bash
# エラー: ja_core_news_trfが見つかりません
# 解決方法: モデルをインストール
uv run python -m spacy download ja_core_news_trf
# または軽量版
uv run python -m spacy download ja_core_news_sm
# またはGINZA（高精度日本語処理）
uv run python -m pip install 'ginza[ja]'
```

#### 2. PDF処理エラー

```bash
# エラー: PDFファイルが開けない
# 解決方法:
# - ファイルパスが正しいか確認
# - PDFファイルが破損していないか確認
# - ファイルが他のプロセスで使用されていないか確認
```

#### 3. 大容量ファイルの処理

```yaml
# config.yamlで調整
pdf_processing:
  processing:
    batch_size: 25        # バッチサイズを小さくする
    parallel_processing: false # 並列処理を無効化
```

#### 4. メモリ不足エラー

- 大容量ファイルは分割して処理
- バッチサイズを小さくする
- 不要なエンティティタイプを無効化

### ログレベルの調整

```yaml
features:
  logging:
    level: "DEBUG"        # 詳細ログ
    log_to_file: true     # ファイル出力
    log_file_path: "debug.log"
```

## 高度な使用例

### 1. カスタム認識器の作成

```yaml
custom_recognizers:
  employee_id:
    enabled: true
    entity_type: "EMPLOYEE_ID"
    patterns:
      - name: "社員番号"
        regex: "EMP[0-9]{6}"
        score: 0.9
      - name: "契約番号"
        regex: "CONT-[A-Z0-9]{8}"
        score: 0.8
```

### 2. 複数設定ファイルの運用

```bash
# ハイライトのみでマスキング
uv run python src/pdf_presidio_processor.py document.pdf --config config/highlighting_only.yaml

# 高精度検出（誤検出を最小化）
uv run python src/pdf_presidio_processor.py document.pdf --config config/high_threshold.yaml

# 電話番号・マイナンバーのみ検出
uv run python src/pdf_presidio_processor.py document.pdf --config config/specific_entities.yaml

# 既存PDF注釈の読み取り
uv run python src/pdf_presidio_processor.py document.pdf --config config/read_mode.yaml --read-mode

# 包括的テスト（全機能有効）
uv run python src/pdf_presidio_processor.py document.pdf --config config/comprehensive_test.yaml

# 低閾値で広範囲検出
uv run python src/pdf_presidio_processor.py document.pdf --config config/low_threshold.yaml

# 詳細ログ付き処理
uv run python src/pdf_presidio_processor.py test_pdfs/ --verbose

# 設定ファイルと詳細ログの組み合わせ
uv run python src/pdf_presidio_processor.py test_pdfs/ --config config/highlighting_only.yaml --verbose
```

### 3. バッチ処理スクリプト例

```bash
#!/bin/bash
# batch_process.sh

# PDF処理
echo "PDF処理開始..."
uv run python src/pdf_presidio_processor.py ./test_pdfs/ --verbose --config config/highlighting_only.yaml

# 追加のPDF処理
echo "高セキュリティ設定での処理..."
uv run python src/pdf_presidio_processor.py ./input_docs/ --config config/high_threshold.yaml

echo "処理完了"
```

## パフォーマンス最適化

### 1. 処理速度の改善

- spaCyモデル: `ja_core_news_sm`を使用（精度は下がるが高速）
- GINZA: `ja_ginza`は標準モデルより高精度だが処理時間は長め
- エンティティタイプ: 必要なもののみ有効化
- 閾値: 高めに設定して誤検出を減らす
- 重複除去: `contain_only`モードで処理速度向上
- バッチサイズ: 小さめの値でメモリ使用量を抑制

**モデル選択の指針:**
- 速度重視: `ja_core_news_sm`
- バランス重視: `ja_core_news_md` または `ja_ginza`
- 精度重視: `ja_ginza_electra` または `ja_core_news_trf`

### 2. メモリ使用量の最適化

```yaml
pdf_processing:
  processing:
    batch_size: 10                    # 小さいバッチサイズ
    parallel_processing: false        # 並列処理無効（メモリ節約）
    skip_processed_files: true        # 処理済みファイルスキップ（重複処理防止）

# spaCyモデルのフォールバック設定
nlp:
  spacy_model: "ja_core_news_sm"      # メインモデル
  fallback_models:                    # フォールバック順序
    - "ja_core_news_sm"
    - "ja_core_news_md"
  auto_download: true                 # モデル自動ダウンロード
```

### 3. 大量ファイル処理

```bash
# フォルダを分割して処理
for dir in folder1 folder2 folder3; do
  uv run python src/pdf_presidio_processor.py $dir/ --config config/highlighting_only.yaml
done
```

## セキュリティとプライバシー

### 1. 機密情報の取り扱い

- バックアップファイルの適切な管理
- 処理済みファイルの確認と保管
- ログファイルの個人情報除去

### 2. 除外設定の活用

```yaml
exclusions:
  text_exclusions:
    - "例："
    - "サンプル"
    - "テスト用"
    - "ダミー"
  file_exclusions:
    - "*_temp.*"
    - "*_test.*"
```

## サポートとリソース

### 設定ファイルサンプル

利用可能な設定ファイル：

**基本設定**：
- `config/highlighting_only.yaml`: ハイライトのみマスキング（注釈なし）
- `config/high_threshold.yaml`: 高閾値設定で誤検出を最小化  
- `config/specific_entities.yaml`: 電話番号・マイナンバーのみ検出
- `config/read_mode.yaml`: 既存PDF注釈の読み取り専用
- `config/comprehensive_test.yaml`: 全機能を有効化したテスト用
- `config/low_threshold.yaml`: 低閾値で広範囲検出

**重複除去設定**：
- `config/deduplication_score.yaml`: スコア優先で重複除去
- `config/deduplication_wider.yaml`: 広い範囲優先で重複除去
- `config/deduplication_entity.yaml`: エンティティタイプ優先で重複除去

**モデル設定**：
- `config/model_test.yaml`: spaCyモデル設定のテスト用

### ドキュメント

- `PyMuPDF_Migration_Summary.md`: PyMuPDF移行に関する情報
- `CLAUDE.md`: 開発環境とプロジェクト概要

### テスト

```bash
# テスト実行
uv run pytest

# 特定のテスト
uv run pytest tests/test_pdf_processor.py -v
```

---

このUSAGE.mdは、PDF個人情報検出・マスキングシステムの包括的な使用方法を示しています。具体的な用途や環境に応じて、設定ファイルやコマンドライン オプションを調整してご使用ください。