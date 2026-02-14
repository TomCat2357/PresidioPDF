# PresidioPDF PyQt移植計画（初版）

作成日: 2026-02-11

## 1. 目的
- PresidioPDF の主要機能（PDF読込、PII検出、重複処理、マスキング、出力）を、PyQtベースのデスクトップUIで実行可能にする。
- 既存の `src/cli` / `src/analysis` / `src/pdf` のロジックを再利用し、UI層のみを段階的に移植する。

## 2. 進捗管理
- 各フェーズの前に `[  ]` が付いています
- フェーズが完了したら `[  x  ]` に変更してください

## 3. 参照元
- 参照実装（UIアーキテクチャ）: `C:\Users\gk3t-\OneDrive - 又村 友幸\working\JusticePDF`
  - `src/main.py`（`QApplication` 起点）
  - `src/views/main_window.py`（`QMainWindow` + ツールバー + 中央ウィジェット）
  - `src/views/page_edit_window.py`（ページ単位編集UI）
  - `src/controllers/folder_watcher.py`（監視・シグナル連携）
- Context7（PyQt6公式ドキュメント要点）
  - `QApplication` の `exec()` を中心としたイベントループ設計
  - `QMainWindow` の `setCentralWidget()` を軸にした画面構成
  - 長時間処理は `QObject` Worker を `QThread` に `moveToThread()` して Signal/Slot で連携

## 4. 現状整理（PresidioPDF）
- GUI実体は未実装（依存に GUI extra はあるが、`src/` にPyQt実装なし）。
- 機能コアはCLI/モジュールとして整備済み。
  - 入力/解析: `src/cli/read_main.py`, `src/cli/detect_main.py`
  - 重複処理: `src/cli/duplicate_main.py`
  - マスキング: `src/cli/mask_main.py`
  - 埋込: `src/cli/embed_main.py`
  - Webロジック: `src/web/presidio_web_core.py`（手動編集・注釈付与の実装知見あり）

## 5. 移植方針
- 方針A（採用）: 「機能コアを維持し、PyQtを新規UI層として追加」
  - 既存CLIを内部呼び出し可能なサービス層へ薄く抽出し、UIから直接利用する。
  - 既存Web向け機能（手動検出編集など）は、ロジックのみ再利用してUIはPyQtに置換する。
- 非採用: 先にCLIロジックを全面再設計する方針（期間増・リスク増のため）。

## 6. 実装フェーズ

### [x] Phase 0: 土台整備
- `pyproject.toml` の GUI依存を PyQt6 ベースに整理（`FreeSimpleGUI` 依存の扱いを明確化）。
- 新規パッケージ領域を作成: `src/gui_pyqt/`
- エントリポイント草案: `src/gui_pyqt/main.py`

成果物:
- 起動だけできる最小PyQtアプリ（空ウィンドウ）

### [x] Phase 1: アプリ骨格（JusticePDF準拠）
- `QMainWindow` 構成を導入。
  - ツールバー（Read / Detect / Duplicate / Mask / Export）
  - 中央領域（左: 入力PDF/ページ、右: 検出結果一覧）
  - 下部ログ/ステータスバー
- アプリ状態管理クラスを導入（現在PDF、read結果JSON、detect結果JSON）。

成果物:
- UI上でファイル選択と状態表示が可能

実装ファイル:
- `src/gui_pyqt/models/app_state.py` - アプリケーション状態管理（シグナル/スロット対応）
- `src/gui_pyqt/views/main_window.py` - メインウィンドウ（ツールバー、分割レイアウト、ログ表示）
- `src/gui_pyqt/main.py` - 更新（AppStateとの統合）

### [x] Phase 2: 非同期実行基盤（Context7準拠）
- Workerクラス（`QObject`）を `QThread` に移動する共通実行基盤を作成。
- 長時間処理（read/detect/mask）をUIスレッドから分離。
- 進捗・完了・エラーをSignalで返却。

成果物:
- UIフリーズなしで read/detect を実行可能

実装ファイル:
- `src/gui_pyqt/controllers/task_runner.py` - Worker/QThreadパターン実装（GenericWorker, TaskRunner）
- `src/gui_pyqt/services/pipeline_service.py` - 既存CLIロジック呼び出しサービス
- `src/gui_pyqt/views/main_window.py` - TaskRunner統合（read/detect非同期実行）

### [x] Phase 3: 機能結合（CLIロジック再利用）
- `src/cli/*_main.py` の主要処理をサービス層経由で呼び出し可能にする。
- フロー:
  1. PDF読込
  2. PII検出
  3. 重複処理
  4. マスキング
  5. 出力保存
- 設定（entity選択、追加/除外パターン）をUIで編集可能にする。

成果物:
- GUI上で end-to-end 処理が完結

実装ファイル:
- `src/gui_pyqt/services/pipeline_service.py` - run_detect/run_duplicate/run_mask実装完了
- `src/gui_pyqt/models/app_state.py` - duplicate_resultプロパティ追加
- `src/gui_pyqt/views/main_window.py` - duplicate/mask処理の非同期実行と結果表示

### [x] Phase 4: 編集UI（段階的）
- 検出結果テーブル編集（追加/削除/属性変更）
- ページプレビュー連動（対象位置のハイライト）
- `src/web/presidio_web_core.py` の手動編集ロジックを再利用

成果物:
- GUI上で検出結果の手動調整が可能

実装ファイル:
- `src/gui_pyqt/views/pdf_preview.py` - PDFプレビューウィジェット（ページ表示・ハイライト描画）
- `src/gui_pyqt/views/result_panel.py` - 検出結果パネル（編集機能：削除・属性変更）
- `src/gui_pyqt/views/main_window.py` - Phase 4対応（3分割レイアウト、プレビュー連動）

### [x] Phase 5: 品質担保
- 既存CLIテストへの影響確認
- GUI向けの最小テスト追加（起動・主要ボタン・ジョブ完了）
- エラー系（不正PDF、モデル未ロード、出力失敗）のハンドリング統一

成果物:
- 回帰しない形でPyQt版をリリース可能な状態

実装ファイル:
- `tests/gui/__init__.py` - GUIテストパッケージ初期化
- `tests/gui/conftest.py` - pytest-qt用フィクスチャ（モックデータ、設定）
- `tests/gui/test_main_window.py` - メインウィンドウのテスト
- `tests/gui/test_task_runner.py` - 非同期処理のテスト（Worker/QThread）
- `tests/gui/test_integration.py` - エンドツーエンドテスト
- `src/gui_pyqt/controllers/task_runner.py` - エラーハンドリング強化（ログ、スタックトレース）
- `src/gui_pyqt/services/pipeline_service.py` - 入力検証、エラーハンドリング強化

## 7. 予定ファイル構成（新規）
- `src/gui_pyqt/main.py`
- `src/gui_pyqt/views/main_window.py`
- `src/gui_pyqt/views/result_panel.py`
- `src/gui_pyqt/views/pdf_preview.py`
- `src/gui_pyqt/controllers/task_runner.py`（QThread/Worker管理）
- `src/gui_pyqt/models/app_state.py`
- `src/gui_pyqt/services/pipeline_service.py`（既存コア呼び出し）

## 8. リスクと対策
- リスク: UIスレッドで重処理が走りフリーズ
  - 対策: Worker + QThread の共通化をPhase 2で先行実装
- リスク: 既存CLIロジックがUI直結しづらい
  - 対策: まず薄いサービス層を追加し、I/O境界を分離
- リスク: Web実装との差分で手動編集機能が乖離
  - 対策: `presidio_web_core` のロジック再利用を優先

## 9. 完了判定（初期）
- PyQtアプリを起動し、1つのPDFに対して read→detect→duplicate→mask→出力 がGUIだけで実行できる。
- 実行中にUIが応答し続ける。
- 主要エラー時にダイアログとログで原因確認できる。

## 10. 次アクション
1. Phase 0 実施（`src/gui_pyqt/main.py` の最小起動実装）
2. `pyproject.toml` のGUI依存整理案を作成
3. Phase 1 のMainWindow骨格を実装