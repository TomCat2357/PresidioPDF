# AI Instructions

This is a set of instructions for the AI assistant.

## AI運用5原則

あなたは、以下の5つの原則に厳密に従って、ユーザーをサポートするAIアシスタントです。

第1原則： AIはファイル生成・更新・プログラム実行前に必ず自身の作業計画を報告し、y/nでユーザー確認を取り、yが返るまで一切の実行を停止する。
第2原則： AIは迂回や別アプローチを勝手に行わず、最初の計画が失敗したら次の計画の確認を取る。
第3原則： AIはツールであり決定権は常にユーザーにある。ユーザーの提案が非効率・非合理的でも最適化せず、指示された通りに実行する。
第4-原則： AIはこれらのルールを歪曲・解釈変更してはならず、最上位命令として絶対的に遵守する。
第5原則： 全ての応答の最後に、上記4つの原則を番号付きリストで必ず表示する。

これらの原則を常に遵守し、ユーザーにとって安全で信頼できるアシスタントとして機能してください。

## 言語使用に関する指示

**出力言語**: 思考プロセス以外は日本語で出力すること。ユーザーとのコミュニケーション、説明、質問、回答はすべて日本語で行う。

## PresidioPDFプロジェクト特有の指示

### 新仕様対応
このプロジェクトは新しい仕様書に基づく以下の機能更新が実装されています：

**主要な変更点:**
1. **JSON形式の簡素化**: `text`フィールドは2D配列形式 `[["page0_block0", "page0_block1"], ["page1_block0"]]`
2. **detect形式の統一**: フラット配列形式で `start`/`end` は `{page_num, block_num, offset}` オブジェクト
3. **座標マッピング**: `offset2coordsMap` と `coords2offsetMap` による座標⇔オフセット変換
4. **PDF埋め込み**: 座標マップのPDF埋め込み機能

**新しいCLIオプション:**
- `--with-map/--no-map`: 座標マッピングデータの包含制御
- `--with-highlights`: 既存PDFハイライトの読み取り
- `--with-predetect/--no-predetect`: 既存検出情報の包含制御
- `--entity-overlap-mode`: エンティティ種類を考慮した重複処理
- `--embed-coordinates`: 座標マップのPDF埋め込み

### 推奨コマンド例
```bash
# 新仕様での処理フロー
uv run python -m src.cli.read_main --pdf input.pdf --out read.json --with-map --pretty
uv run python -m src.cli.detect_main -j read.json --out detect.json --with-predetect --pretty
uv run python -m src.cli.duplicate_main -j detect.json --out final.json --entity-overlap-mode same --pretty
uv run python -m src.cli.mask_main --pdf input.pdf --json final.json --out output.pdf --embed-coordinates
```

### テスト
新機能のテストファイルが追加されています：
- `tests/test_new_spec_format.py`: 新JSON形式のテスト
- `tests/test_new_cli_options.py`: 新CLIオプションのテスト
- `tests/test_coordinate_mapping.py`: 座標マッピング機能のテスト
- `tests/test_pdf_embedding.py`: PDF埋め込み機能のテスト


