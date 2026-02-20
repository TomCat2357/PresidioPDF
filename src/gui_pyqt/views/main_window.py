"""
PresidioPDF PyQt - メインウィンドウ

Phase 1: アプリ骨格（JusticePDF準拠）
- QMainWindow構成
- ツールバー（Read / Detect / Duplicate / Mask / Export）
- 中央領域（左: 入力PDF/ページ、右: 検出結果一覧）
- 下部ログ/ステータスバー

Phase 4: 編集UI
- PDFプレビュー表示
- 検出結果の編集機能（削除・属性変更）
- プレビュー連動（選択時のハイライト）
"""

import logging
import json
import copy
import shutil
import fitz
from pathlib import Path
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTextEdit,
    QLabel,
    QToolBar,
    QToolButton,
    QMenu,
    QFileDialog,
    QMessageBox,
    QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QUrl, QEvent, QObject
from PyQt6.QtGui import QAction, QDesktopServices, QCloseEvent

logger = logging.getLogger(__name__)

from ..models.app_state import AppState
from ..controllers.task_runner import TaskRunner
from ..services.pipeline_service import PipelineService
from ..services.detect_config_service import DetectConfigService
from .pdf_preview import PDFPreviewWidget
from .result_panel import ResultPanel
from .config_dialog import DetectConfigDialog


class MainWindow(QMainWindow):
    """メインウィンドウクラス"""
    EMBEDDED_MAPPING_FILENAME = "presidiopdf_mapping.json"
    SIDECAR_SUFFIX = ".presidiopdf.json"

    @staticmethod
    def _sidecar_path_for(pdf_path: Path) -> Path:
        return pdf_path.parent / f"{pdf_path.stem}{MainWindow.SIDECAR_SUFFIX}"

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state

        # Phase 2: TaskRunnerの初期化
        self.task_runner = TaskRunner(self)
        self.current_task = None  # 現在実行中のタスク名

        # 全プレビューエンティティを保持（選択状態管理用）
        self._all_preview_entities: List[Dict] = []

        # GUI検出設定（$HOME/.presidio/config.json）
        self.detect_config_service = DetectConfigService(Path.home())
        try:
            self.enabled_detect_entities = self.detect_config_service.ensure_config_file()
            duplicate_settings = self.detect_config_service.load_duplicate_settings()
            self.duplicate_entity_overlap_mode = duplicate_settings["entity_overlap_mode"]
            self.duplicate_overlap_mode = duplicate_settings["overlap"]
            self.spacy_model = self.detect_config_service.load_spacy_model()
        except Exception as e:
            logger.warning(f"検出設定の初期化に失敗: {e}")
            self.enabled_detect_entities = list(DetectConfigService.ENTITY_TYPES)
            self.duplicate_entity_overlap_mode = "any"
            self.duplicate_overlap_mode = "overlap"
            self.spacy_model = DetectConfigService.DEFAULT_SPACY_MODEL

        # Detect実行スコープの管理
        self._detect_scope = "all"
        self._detect_target_pages: Optional[List[int]] = None
        self._detect_base_result: Optional[Dict[str, Any]] = None
        self._duplicate_scope = "all"
        self._duplicate_target_pages: Optional[List[int]] = None
        self._duplicate_base_result: Optional[Dict[str, Any]] = None
        self._is_dirty = False

        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        """UIの初期化"""
        # ウィンドウの基本設定
        self.setWindowTitle("PresidioPDF")
        self.setGeometry(100, 100, 1400, 900)

        # ツールバーの作成
        self.create_toolbar()

        # 中央ウィジェットの作成
        self.create_central_widget()

        # ステータスバーの作成
        self.create_statusbar()
        self._setup_pdf_drop_targets()

    def _setup_pdf_drop_targets(self):
        """アプリ全域でPDFドロップを受け付ける"""
        self.setAcceptDrops(True)
        self.installEventFilter(self)
        for widget in self.findChildren(QWidget):
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)

    @staticmethod
    def _extract_dropped_pdf_path(event) -> Optional[str]:
        """ドラッグ/ドロップイベントから最初のローカルPDFパスを取り出す"""
        mime_data = event.mimeData() if event is not None else None
        if mime_data is None or not mime_data.hasUrls():
            return None

        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            file_path = url.toLocalFile()
            if str(file_path).lower().endswith(".pdf"):
                return str(file_path)
        return None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """アプリ内のどこにドロップしてもPDF読込へ接続する"""
        event_type = event.type()
        if event_type in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            file_path = self._extract_dropped_pdf_path(event)
            if file_path is not None:
                event.acceptProposedAction()
                return True
        elif event_type == QEvent.Type.Drop:
            file_path = self._extract_dropped_pdf_path(event)
            if file_path is not None:
                event.acceptProposedAction()
                self.on_pdf_dropped(file_path)
                return True
        return super().eventFilter(watched, event)

    def create_toolbar(self):
        """ツールバーの作成"""
        toolbar = QToolBar("メインツールバー")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # アクションの定義

        # 開く
        open_action = QAction("開く", self)
        open_action.setStatusTip("PDFファイルを開く（マッピングがあれば自動読込）")
        open_action.triggered.connect(self.on_open_pdf)
        toolbar.addAction(open_action)

        # ファイルを閉じる
        close_pdf_action = QAction("閉じる", self)
        close_pdf_action.setStatusTip("現在開いているPDFファイルを閉じる")
        close_pdf_action.triggered.connect(self.on_close_pdf)
        toolbar.addAction(close_pdf_action)
        self.close_pdf_action = close_pdf_action

        # 設定（検出/重複設定）
        config_action = QAction("設定", self)
        config_action.setStatusTip(
            f"検出対象と重複削除設定（{DetectConfigService.DISPLAY_FILE_NAME}）"
        )
        config_action.triggered.connect(self.on_open_config_dialog)
        toolbar.addAction(config_action)
        self.config_action = config_action

        # Read（内部的に保持、ツールバーには非表示）
        read_action = QAction("📖 Read", self)
        read_action.triggered.connect(self.on_read)
        self.read_action = read_action

        # 対象検出（ぶら下がりメニュー）
        self.detect_current_action = QAction("表示ページ", self)
        self.detect_current_action.triggered.connect(self.on_detect_current_page)

        self.detect_all_action = QAction("全ページ", self)
        self.detect_all_action.triggered.connect(self.on_detect_all_pages)

        detect_menu = QMenu(self)
        detect_menu.addAction(self.detect_current_action)
        detect_menu.addAction(self.detect_all_action)

        detect_button = QToolButton(self)
        detect_button.setText("対象検出")
        detect_button.setToolTip("個人情報（PII）を検出")
        detect_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        detect_button.setMenu(detect_menu)
        toolbar.addWidget(detect_button)
        self.detect_button = detect_button

        # 対象削除（自動検出のみ、ぶら下がりメニュー）
        self.target_delete_current_action = QAction("表示ページ", self)
        self.target_delete_current_action.triggered.connect(self.on_target_delete_current_page)

        self.target_delete_all_action = QAction("全ページ", self)
        self.target_delete_all_action.triggered.connect(self.on_target_delete_all_pages)

        target_delete_menu = QMenu(self)
        target_delete_menu.addAction(self.target_delete_current_action)
        target_delete_menu.addAction(self.target_delete_all_action)

        target_delete_button = QToolButton(self)
        target_delete_button.setText("対象削除")
        target_delete_button.setToolTip("自動検出項目を削除")
        target_delete_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        target_delete_button.setMenu(target_delete_menu)
        toolbar.addWidget(target_delete_button)
        self.target_delete_button = target_delete_button

        # 重複削除（ぶら下がりメニュー）
        self.duplicate_current_action = QAction("表示ページ", self)
        self.duplicate_current_action.triggered.connect(self.on_duplicate_current_page)

        self.duplicate_all_action = QAction("全ページ", self)
        self.duplicate_all_action.triggered.connect(self.on_duplicate_all_pages)

        duplicate_menu = QMenu(self)
        duplicate_menu.addAction(self.duplicate_current_action)
        duplicate_menu.addAction(self.duplicate_all_action)

        duplicate_button = QToolButton(self)
        duplicate_button.setText("重複削除")
        duplicate_button.setToolTip("重複する検出結果を処理")
        duplicate_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        duplicate_button.setMenu(duplicate_menu)
        toolbar.addWidget(duplicate_button)
        self.duplicate_button = duplicate_button

        # 保存（PDF + JSONマッピング）
        save_action = QAction("保存", self)
        save_action.setStatusTip("PDFとサイドカーJSONマッピングを保存")
        save_action.triggered.connect(self.on_save)
        toolbar.addAction(save_action)
        self.save_action = save_action

        # エクスポート（ぶら下がりメニュー）
        self.export_annotations_action = QAction("アノテーション付き", self)
        self.export_annotations_action.triggered.connect(self.on_export_annotations)

        self.export_mask_action = QAction("マスク", self)
        self.export_mask_action.triggered.connect(self.on_mask)

        self.export_mask_as_image_action = QAction("マスク（画像として保存）", self)
        self.export_mask_as_image_action.triggered.connect(self.on_export_mask_as_image)
        self.export_marked_as_image_action = QAction("マーク（画像として保存）", self)
        self.export_marked_as_image_action.triggered.connect(self.on_export_marked_as_image)

        export_menu = QMenu(self)
        export_menu.addAction(self.export_annotations_action)
        export_menu.addAction(self.export_mask_action)
        export_menu.addAction(self.export_mask_as_image_action)
        export_menu.addAction(self.export_marked_as_image_action)

        export_button = QToolButton(self)
        export_button.setText("エクスポート")
        export_button.setToolTip("検出結果を各モードで保存")
        export_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        export_button.setMenu(export_menu)
        toolbar.addWidget(export_button)
        self.export_button = export_button

        # 初期状態では一部のアクションを無効化
        self.update_action_states()

    def create_central_widget(self):
        """中央ウィジェットの作成（Phase 4: 2分割レイアウト）"""
        # メイン水平スプリッター（2分割: プレビュー、検出結果）
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左側パネル: PDFプレビュー（Phase 4）
        self.pdf_preview = PDFPreviewWidget()
        main_splitter.addWidget(self.pdf_preview)

        # 右側パネル: 検出結果一覧（Phase 4: 編集機能付き）
        self.result_panel = ResultPanel()
        main_splitter.addWidget(self.result_panel)

        # 分割比率（プレビュー:検出結果 = 6:5）
        main_splitter.setSizes([600, 500])

        # 全体の縦分割（メイン領域 + ログ領域）
        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.addWidget(main_splitter)

        # ログ領域
        log_panel = self.create_log_panel()
        vertical_splitter.addWidget(log_panel)

        # 分割比率（メイン:ログ = 5:1）
        vertical_splitter.setSizes([750, 150])

        self.setCentralWidget(vertical_splitter)


    def create_log_panel(self) -> QWidget:
        """ログ/メッセージ表示パネル"""
        panel = QWidget()
        layout = QVBoxLayout()

        log_label = QLabel("ログ:")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("処理ログがここに表示されます")
        layout.addWidget(self.log_text)

        panel.setLayout(layout)
        return panel

    def create_statusbar(self):
        """ステータスバーの作成"""
        self.statusBar().showMessage("準備完了")

    def connect_signals(self):
        """AppStateとTaskRunnerのシグナルと接続"""
        # AppStateのシグナル
        self.app_state.pdf_path_changed.connect(self.on_pdf_path_changed)
        self.app_state.read_result_changed.connect(self.on_read_result_changed)
        self.app_state.detect_result_changed.connect(self.on_detect_result_changed)
        self.app_state.duplicate_result_changed.connect(self.on_duplicate_result_changed)
        self.app_state.status_message_changed.connect(self.on_status_message_changed)

        # Phase 2: TaskRunnerのシグナル
        self.task_runner.progress.connect(self.on_task_progress)
        self.task_runner.finished.connect(self.on_task_finished)
        self.task_runner.error.connect(self.on_task_error)
        self.task_runner.started.connect(self.on_task_started)
        self.task_runner.running_state_changed.connect(self.on_task_running_state_changed)

        # ResultPanelのシグナル
        self.result_panel.entity_selected.connect(self.on_entity_selected)
        self.result_panel.entity_deleted.connect(self.on_entity_deleted)
        self.result_panel.entity_updated.connect(self.on_entity_updated)
        self.result_panel.entity_added.connect(self.on_entity_added)
        self.result_panel.select_current_page_requested.connect(
            self.on_select_current_page_requested
        )

        # PDFプレビューからの逆方向連携
        self.pdf_preview.entity_clicked.connect(self.on_preview_entity_clicked)
        self.pdf_preview.text_selected.connect(self.on_text_selected)
        self.pdf_preview.pdf_file_dropped.connect(self.on_pdf_dropped)

    # =========================================================================
    # アクションハンドラー（Phase 1: スタブ実装）
    # =========================================================================

    def on_open_pdf(self):
        """PDFファイルを開く（埋め込みマッピングがあれば復元、なければRead自動実行）"""
        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        initial_dir = self.detect_config_service.load_last_directory("open")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "PDFファイルを選択",
            initial_dir,
            "PDF Files (*.pdf);;All Files (*)"
        )

        if not file_path:
            return
        self.detect_config_service.save_last_directory("open", str(Path(file_path).parent))
        if not self._maybe_proceed_with_unsaved():
            return
        self._open_pdf_path(Path(file_path))

    def on_close_pdf(self):
        """現在開いているPDFファイルを閉じる"""
        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        if not self.app_state.has_pdf():
            return

        if not self._maybe_proceed_with_unsaved():
            return

        closed_pdf = self.app_state.pdf_path
        self.app_state.clear()
        self._reset_detect_scope_context()
        self._reset_duplicate_scope_context()
        self._set_dirty(False)
        self.update_action_states()
        if closed_pdf:
            self.log_message(f"PDFファイルを閉じました: {closed_pdf}")

    def on_pdf_dropped(self, file_path: str):
        """左ペインへドロップされたPDFを開く"""
        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        if not file_path:
            return
        dropped_path = Path(file_path)
        if dropped_path.suffix.lower() != ".pdf":
            return

        current_pdf = self.app_state.pdf_path
        if isinstance(current_pdf, Path):
            try:
                if dropped_path.resolve() == current_pdf.resolve():
                    return
            except Exception:
                if str(dropped_path) == str(current_pdf):
                    return

        if not self._maybe_proceed_with_unsaved():
            return
        self._open_pdf_path(dropped_path)

    def _open_pdf_path(self, pdf_path: Path):
        """指定パスのPDFを読み込む"""
        self.app_state.pdf_path = pdf_path
        # PDF切り替え時は前回結果をクリア
        self.app_state.read_result = None
        self.app_state.detect_result = None
        self.app_state.duplicate_result = None
        self.log_message(f"PDFファイルを選択: {pdf_path}")
        self._set_dirty(False)
        self.update_action_states()

        # マッピングがあれば復元（サイドカー優先、埋め込みは後方互換）
        if self._load_mapping_for_pdf(pdf_path):
            self.update_action_states()
            return

        # マッピングがない場合はRead処理を自動実行
        self._auto_read()

    def _set_dirty(self, is_dirty: bool):
        """未保存状態フラグを更新"""
        self._is_dirty = bool(is_dirty)

    def _confirm_unsaved_changes(self) -> str:
        """未保存データの扱いを確認する"""
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("未保存の変更")
        dialog.setText("未保存の変更があります。")
        dialog.setInformativeText("保存してから続行しますか？")

        save_button = dialog.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
        discard_button = dialog.addButton("破棄", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = dialog.addButton("キャンセル", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(save_button)
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked == save_button:
            return "save"
        if clicked == discard_button:
            return "discard"
        if clicked == cancel_button:
            return "cancel"
        return "cancel"

    def _maybe_proceed_with_unsaved(self) -> bool:
        """未保存状態に応じて続行可否を返す"""
        if not self._is_dirty:
            return True

        action = self._confirm_unsaved_changes()
        if action == "discard":
            return True
        if action == "save":
            return self._save_current_workflow()
        return False

    def closeEvent(self, event: QCloseEvent):
        """ウィンドウ終了時に未保存確認を行う"""
        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            event.ignore()
            return

        if not self._maybe_proceed_with_unsaved():
            event.ignore()
            return
        event.accept()

    def _auto_read(self):
        """PDF選択後にRead処理を自動実行"""
        if not self.app_state.has_pdf():
            return
        if self.task_runner.is_running():
            self.log_message("別のタスク実行中のためRead自動実行をスキップ")
            return
        self.on_read()

    def on_read(self):
        """Read処理（非同期実行）"""
        if not self.app_state.has_pdf():
            QMessageBox.warning(self, "警告", "PDFファイルが選択されていません")
            return

        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        self.log_message("Read処理を開始...")

        # TaskRunnerで非同期実行
        self.current_task = "read"
        self.task_runner.start_task(
            PipelineService.run_read,
            self.app_state.pdf_path,
            True  # include_coordinate_map
        )

    def on_open_config_dialog(self):
        """検出設定ダイアログを表示"""
        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        try:
            current_enabled = self.detect_config_service.ensure_config_file()
            dialog_enabled_entities = (
                list(current_enabled)
                if isinstance(current_enabled, list)
                else list(self.enabled_detect_entities)
            )
            duplicate_settings = self.detect_config_service.load_duplicate_settings()
            self.duplicate_entity_overlap_mode = duplicate_settings["entity_overlap_mode"]
            self.duplicate_overlap_mode = duplicate_settings["overlap"]
            self.spacy_model = self.detect_config_service.load_spacy_model()
            installed_models = DetectConfigService.get_installed_spacy_models()

            dialog = DetectConfigDialog(
                entity_types=DetectConfigService.ENTITY_TYPES,
                enabled_entities=dialog_enabled_entities,
                config_path=self.detect_config_service.config_path,
                duplicate_entity_overlap_mode=self.duplicate_entity_overlap_mode,
                duplicate_overlap_mode=self.duplicate_overlap_mode,
                spacy_model=self.spacy_model,
                installed_models=installed_models,
                all_models=DetectConfigService.SPACY_MODELS,
                parent=self,
            )
            if dialog.import_button:
                dialog.import_button.clicked.connect(
                    lambda: self._on_import_config_clicked(dialog)
                )
            if dialog.export_button:
                dialog.export_button.clicked.connect(
                    lambda: self._on_export_config_clicked(dialog)
                )
            if dialog.open_json_button:
                dialog.open_json_button.clicked.connect(
                    lambda: self._on_open_json_config_clicked(dialog)
                )

            dialog.exec()

            # 設定はダイアログでリアルタイム保存されるため、終了後に再読込する
            self.enabled_detect_entities = self.detect_config_service.ensure_config_file()
            saved_duplicate_settings = self.detect_config_service.load_duplicate_settings()
            self.duplicate_entity_overlap_mode = saved_duplicate_settings["entity_overlap_mode"]
            self.duplicate_overlap_mode = saved_duplicate_settings["overlap"]
            self.spacy_model = self.detect_config_service.load_spacy_model()
            self.log_message(
                f"検出設定を保存: {len(self.enabled_detect_entities)}件を有効化 "
                f"({self.detect_config_service.config_path.name}), "
                f"モデル={self.spacy_model}, "
                f"重複設定=entity_overlap_mode:{self.duplicate_entity_overlap_mode}, "
                f"overlap:{self.duplicate_overlap_mode}"
            )
        except Exception as e:
            logger.exception("検出設定ダイアログの表示/保存に失敗")
            QMessageBox.critical(
                self,
                "エラー",
                f"設定画面の表示または保存に失敗しました: {e}",
            )

    def _on_open_json_config_clicked(self, dialog: DetectConfigDialog):
        """検出設定ファイルを既定アプリで開く（ダイアログの状態を先に保存）"""
        try:
            # ダイアログ上の最新状態を書き出してから開く
            dialog.save_current_to_file()
            json_path = self.detect_config_service.config_path
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(json_path)))
            if not opened:
                QMessageBox.warning(
                    self,
                    "警告",
                    f"{DetectConfigService.DISPLAY_FILE_NAME} を開けませんでした:\n{json_path}",
                )
                return
            self.log_message(
                f"{DetectConfigService.DISPLAY_FILE_NAME} を開きました: {json_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "エラー",
                f"{DetectConfigService.DISPLAY_FILE_NAME} を開けませんでした: {e}",
            )

    def _on_import_config_clicked(self, dialog: DetectConfigDialog):
        """設定ファイルのインポート"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "インポートするJSONを選択",
            str(self.detect_config_service.config_path.parent),
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        try:
            imported_entities = self.detect_config_service.import_from(Path(file_path))
            self.enabled_detect_entities = imported_entities
            imported_duplicate_settings = self.detect_config_service.load_duplicate_settings()
            self.duplicate_entity_overlap_mode = imported_duplicate_settings["entity_overlap_mode"]
            self.duplicate_overlap_mode = imported_duplicate_settings["overlap"]
            self.spacy_model = self.detect_config_service.load_spacy_model()
            dialog.set_enabled_entities(imported_entities)
            dialog.set_duplicate_settings(
                self.duplicate_entity_overlap_mode,
                self.duplicate_overlap_mode,
            )
            dialog.set_spacy_model(self.spacy_model)
            self.log_message(
                f"設定インポート: {file_path} -> {self.detect_config_service.config_path}"
            )
            self.statusBar().showMessage("設定をインポートしました")
        except Exception as e:
            QMessageBox.critical(
                self,
                "エラー",
                f"設定インポートに失敗しました: {e}",
            )

    def _on_export_config_clicked(self, dialog: DetectConfigDialog):
        """設定ファイルのエクスポート"""
        default_path = self.detect_config_service.config_path
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "エクスポート先を選択",
            str(default_path),
            "JSON Files (*.json);;All Files (*)",
        )
        if not output_path:
            return

        try:
            export_target = Path(output_path)
            if export_target.suffix.lower() != ".json":
                export_target = export_target.with_suffix(".json")

            # ダイアログ上の最新チェック状態を同一フォルダ設定へ反映してから出力
            current_entities = dialog.get_enabled_entities()
            self.enabled_detect_entities = self.detect_config_service.save_enabled_entities(
                current_entities
            )
            duplicate_settings = dialog.get_duplicate_settings()
            saved_duplicate_settings = self.detect_config_service.save_duplicate_settings(
                duplicate_settings["entity_overlap_mode"],
                duplicate_settings["overlap"],
            )
            self.duplicate_entity_overlap_mode = saved_duplicate_settings["entity_overlap_mode"]
            self.duplicate_overlap_mode = saved_duplicate_settings["overlap"]
            exported_path = self.detect_config_service.export_to(export_target)
            self.log_message(f"設定エクスポート: {exported_path}")
            self.statusBar().showMessage("設定をエクスポートしました")
        except Exception as e:
            QMessageBox.critical(
                self,
                "エラー",
                f"設定エクスポートに失敗しました: {e}",
            )

    def on_detect(self):
        """互換: 全ページ検出を実行"""
        self.on_detect_all_pages()

    def on_detect_all_pages(self):
        """全ページを対象にDetect処理を実行"""
        self._start_detect(scope="all", page_filter=None)

    def on_detect_current_page(self):
        """表示中ページのみを対象にDetect処理を実行"""
        current_page = int(getattr(self.pdf_preview, "current_page_num", 0) or 0)
        self._start_detect(scope="current_page", page_filter=[current_page])

    def _start_detect(self, scope: str, page_filter: Optional[List[int]]):
        """Detect処理（スコープ指定）"""
        if not self.app_state.has_read_result():
            QMessageBox.warning(self, "警告", "Read処理が完了していません")
            return

        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        target_desc = "全ページ" if scope == "all" else f"表示ページ({page_filter[0] + 1}ページ目)"
        self.log_message(
            f"Detect処理を開始... 対象={target_desc}, "
            f"有効エンティティ={len(self.enabled_detect_entities)}件"
        )

        # 現在の結果一覧から手動マークを抽出し、再検出時も保持する
        read_input = self._build_read_result_for_detect()

        self._detect_scope = scope
        self._detect_target_pages = list(page_filter) if page_filter else None
        self._detect_base_result = (
            copy.deepcopy(self.app_state.detect_result)
            if scope == "current_page" and self.app_state.detect_result
            else None
        )

        task_kwargs: Dict[str, Any] = {
            "entities": list(self.enabled_detect_entities),
            "model_names": (self.spacy_model,),
        }
        add_patterns, omit_patterns = self.detect_config_service.load_custom_patterns()
        if add_patterns:
            task_kwargs["add_patterns"] = add_patterns
        if omit_patterns:
            task_kwargs["exclude_patterns"] = omit_patterns
        if add_patterns or omit_patterns:
            self.log_message(
                "追加/除外設定を反映: "
                f"add={len(add_patterns)}件, ommit={len(omit_patterns)}件"
            )
        if page_filter:
            task_kwargs["page_filter"] = list(page_filter)

        # TaskRunnerで非同期実行
        self.current_task = "detect"
        self.task_runner.start_task(
            PipelineService.run_detect,
            read_input,
            **task_kwargs,
        )

    def on_duplicate(self):
        """互換: 全ページ重複削除を実行"""
        self.on_duplicate_all_pages()

    def on_duplicate_all_pages(self):
        """全ページを対象に重複削除を実行"""
        self._start_duplicate(scope="all", page_filter=None)

    def on_duplicate_current_page(self):
        """表示ページのみを対象に重複削除を実行"""
        current_page = int(getattr(self.pdf_preview, "current_page_num", 0) or 0)
        self._start_duplicate(scope="current_page", page_filter=[current_page])

    def _start_duplicate(self, scope: str, page_filter: Optional[List[int]]):
        if not self.app_state.has_detect_result():
            QMessageBox.warning(self, "警告", "Detect処理が完了していません")
            return

        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        detect_result = copy.deepcopy(self.app_state.detect_result or {})
        detect_list = detect_result.get("detect", [])
        if not isinstance(detect_list, list):
            detect_list = []

        self._duplicate_scope = scope
        self._duplicate_target_pages = list(page_filter) if page_filter else None
        self._duplicate_base_result = (
            copy.deepcopy(self.app_state.detect_result)
            if scope == "current_page" and self.app_state.detect_result
            else None
        )

        if page_filter:
            target_pages = set(int(page_num) for page_num in page_filter)
            scoped_detect = [
                entity
                for entity in detect_list
                if self._entity_page_num(entity) in target_pages
            ]
            detect_result["detect"] = scoped_detect
            target_desc = f"表示ページ({page_filter[0] + 1}ページ目)"
        else:
            target_desc = "全ページ"

        self.log_message(
            "Duplicate処理を開始... "
            f"対象={target_desc}, "
            f"(entity_overlap_mode={self.duplicate_entity_overlap_mode}, "
            f"overlap={self.duplicate_overlap_mode})"
        )

        self.current_task = "duplicate"
        self.task_runner.start_task(
            PipelineService.run_duplicate,
            detect_result,
            overlap=self.duplicate_overlap_mode,
            entity_overlap_mode=self.duplicate_entity_overlap_mode,
        )

    def on_target_delete_current_page(self):
        """表示ページの自動検出項目のみ削除"""
        current_page = int(getattr(self.pdf_preview, "current_page_num", 0) or 0)
        self._delete_auto_entities(scope="current_page", page_filter=[current_page])

    def on_target_delete_all_pages(self):
        """全ページの自動検出項目のみ削除"""
        self._delete_auto_entities(scope="all", page_filter=None)

    def _delete_auto_entities(self, scope: str, page_filter: Optional[List[int]]):
        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        entities = self.result_panel.get_entities()
        if not isinstance(entities, list) or not entities:
            QMessageBox.warning(self, "警告", "削除対象がありません")
            return

        target_pages = set(int(page_num) for page_num in (page_filter or []))
        kept_entities: List[Dict[str, Any]] = []
        removed_count = 0
        for entity in entities:
            page_num = self._entity_page_num(entity)
            in_scope = scope == "all" or page_num in target_pages
            is_auto = not self._is_manual_entity(entity)
            if in_scope and is_auto:
                removed_count += 1
                continue
            kept_entities.append(copy.deepcopy(entity))

        if removed_count == 0:
            self.log_message("削除対象の自動検出項目はありませんでした")
            return

        self.result_panel.entities = kept_entities
        self.result_panel.update_table()
        self.result_panel.on_selection_changed()
        self._sync_all_result_states_from_entities(kept_entities)

        current_result = self._get_current_result()
        if current_result:
            self._highlight_all_entities(current_result)
        else:
            self._all_preview_entities = []
            self.pdf_preview.set_highlighted_entities([])

        target_desc = "全ページ" if scope == "all" else f"表示ページ({page_filter[0] + 1}ページ目)"
        self.log_message(f"対象削除を実行: {target_desc}, 自動項目 {removed_count}件を削除")
        self._set_dirty(True)
        self.update_action_states()

    def on_mask(self):
        """Mask処理（Phase 3: 非同期実行）"""
        detect_or_dup_result = self._get_export_source_result()

        if not detect_or_dup_result:
            QMessageBox.warning(self, "警告", "Detect処理が完了していません")
            return

        if not self.app_state.has_pdf():
            QMessageBox.warning(self, "警告", "PDFファイルが選択されていません")
            return

        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        output_pdf_path = self._select_output_pdf_path("マスキング結果の保存先", "_masked")
        if not output_pdf_path:
            return

        self.log_message("Mask処理を開始...")

        # TaskRunnerで非同期実行
        self.current_task = "mask"
        self.task_runner.start_task(
            PipelineService.run_mask,
            detect_or_dup_result,
            self.app_state.pdf_path,
            output_pdf_path,
        )

    def on_export(self):
        """互換: アノテーション付きエクスポートを実行"""
        self.on_export_annotations()

    def on_export_annotations(self):
        """検出結果を注釈付きPDFとしてエクスポート"""
        detect_or_dup_result = self._get_export_source_result()
        if not detect_or_dup_result:
            QMessageBox.warning(self, "警告", "Detect処理が完了していません")
            return
        if not self.app_state.has_pdf():
            QMessageBox.warning(self, "警告", "PDFファイルが選択されていません")
            return
        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        output_pdf_path = self._select_output_pdf_path(
            "注釈付きPDFの保存先",
            "_annotations",
        )
        if not output_pdf_path:
            return

        self.log_message("アノテーション付きエクスポートを開始...")
        self.current_task = "export_annotations"
        self.task_runner.start_task(
            PipelineService.run_export_annotations,
            detect_or_dup_result,
            self.app_state.pdf_path,
            output_pdf_path,
        )

    def on_export_mask_as_image(self):
        """検出結果をマスクし、画像のみPDFとして保存"""
        detect_or_dup_result = self._get_export_source_result()
        if not detect_or_dup_result:
            QMessageBox.warning(self, "警告", "Detect処理が完了していません")
            return
        if not self.app_state.has_pdf():
            QMessageBox.warning(self, "警告", "PDFファイルが選択されていません")
            return
        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        output_pdf_path = self._select_output_pdf_path(
            "マスク（画像として保存）の保存先",
            "_masked_image",
        )
        if not output_pdf_path:
            return
        dpi = self._select_export_dpi()
        if dpi is None:
            return

        self.log_message("マスク（画像として保存）を開始...")
        self.current_task = "mask_as_image"
        self.task_runner.start_task(
            PipelineService.run_mask_as_image,
            detect_or_dup_result,
            self.app_state.pdf_path,
            output_pdf_path,
            None,
            dpi,
        )

    def on_export_marked_as_image(self):
        """検出結果のマークを半透明で重ね、画像のみPDFとして保存"""
        detect_or_dup_result = self._get_export_source_result()
        if not detect_or_dup_result:
            QMessageBox.warning(self, "警告", "Detect処理が完了していません")
            return
        if not self.app_state.has_pdf():
            QMessageBox.warning(self, "警告", "PDFファイルが選択されていません")
            return
        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        output_pdf_path = self._select_output_pdf_path(
            "マーク（画像として保存）の保存先",
            "_marked_image",
        )
        if not output_pdf_path:
            return
        dpi = self._select_export_dpi()
        if dpi is None:
            return

        self.log_message("マーク（画像として保存）を開始...")
        self.current_task = "marked_as_image"
        self.task_runner.start_task(
            PipelineService.run_export_marked_as_image,
            detect_or_dup_result,
            self.app_state.pdf_path,
            output_pdf_path,
            dpi,
        )

    def on_save(self):
        """保存処理（PDF + サイドカーJSONマッピング）"""
        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return
        self._save_current_workflow()

    def _save_current_workflow(self) -> bool:
        """保存処理（PDF + サイドカーJSONマッピング）を実行し成否を返す"""
        if not self.app_state.has_pdf():
            QMessageBox.warning(self, "警告", "PDFファイルが選択されていません")
            return False

        default_name = self.app_state.pdf_path.stem + "_saved.pdf"
        save_dir = self.detect_config_service.load_last_directory("save")
        initial_save = str(Path(save_dir) / default_name) if save_dir else default_name

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存先を選択",
            initial_save,
            "PDF Files (*.pdf);;All Files (*)"
        )

        if not output_path:
            return False
        self.detect_config_service.save_last_directory("save", str(Path(output_path).parent))

        try:
            # マッピング未生成時はreadを同期実行して補完
            if not self.app_state.has_read_result():
                self.log_message("Read結果がないため、マッピング生成を実行します...")
                self.app_state.read_result = PipelineService.run_read(
                    self.app_state.pdf_path,
                    True,
                )

            out_pdf = Path(output_path)
            if out_pdf.suffix.lower() != ".pdf":
                out_pdf = out_pdf.with_suffix(".pdf")

            # 1) PDF保存
            shutil.copy2(self.app_state.pdf_path, out_pdf)

            # 2) サイドカーJSONマッピングを書き出し
            from src.cli.common import sha256_pdf_content
            mapping_payload = self._build_mapping_payload(out_pdf)
            mapping_payload["content_hash"] = sha256_pdf_content(str(out_pdf))

            sidecar_path = self._sidecar_path_for(out_pdf)
            sidecar_path.write_text(
                json.dumps(mapping_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            self.log_message(f"保存完了: {out_pdf}")
            self.log_message(f"サイドカーマッピング保存完了: {sidecar_path}")
            self.statusBar().showMessage("保存しました")
            self._set_dirty(False)
            return True

        except Exception as e:
            error_msg = f"保存中にエラーが発生しました: {str(e)}"
            self.log_message(error_msg)
            QMessageBox.critical(self, "エラー", error_msg)
            return False

    def on_save_session(self):
        """後方互換のエイリアス"""
        self.on_save()

    def on_load_session(self):
        """セッション読込処理（保存したセッションの復元）"""
        # 読込ファイルを選択
        initial_dir = self.detect_config_service.load_last_directory("session")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "セッションファイルを選択",
            initial_dir,
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return
        self.detect_config_service.save_last_directory("session", str(Path(file_path).parent))

        try:
            # JSONファイルを読み込み
            with open(file_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            # PDFパスを復元
            pdf_path_str = session_data.get("pdf_path")
            if pdf_path_str:
                pdf_path = Path(pdf_path_str)
                if pdf_path.exists():
                    self.app_state.pdf_path = pdf_path
                else:
                    QMessageBox.warning(
                        self,
                        "警告",
                        f"PDFファイルが見つかりません:\n{pdf_path_str}\n\nセッションは読み込みますが、PDFプレビューは利用できません。"
                    )

            # 各結果を復元
            self.app_state.read_result = session_data.get("read_result")
            self.app_state.detect_result = session_data.get("detect_result")
            self.app_state.duplicate_result = session_data.get("duplicate_result")

            self.log_message(f"セッション読込完了: {file_path}")
            self.statusBar().showMessage("セッションを読み込みました")
            self._set_dirty(True)

            # UI状態を更新
            self.update_action_states()

        except Exception as e:
            error_msg = f"セッション読込中にエラーが発生しました: {str(e)}"
            self.log_message(error_msg)
            QMessageBox.critical(self, "エラー", error_msg)

    # =========================================================================
    # シグナルスロット
    # =========================================================================

    def on_pdf_path_changed(self, pdf_path: Optional[Path]):
        """PDFパスが変更された"""
        if pdf_path:
            self.statusBar().showMessage(f"PDFファイル: {pdf_path.name}")
            # Phase 4: PDFプレビューに読み込み
            self.pdf_preview.load_pdf(str(pdf_path))
        else:
            self.statusBar().showMessage("PDFファイル: （未選択）")
            self.pdf_preview.close_pdf()

    def on_read_result_changed(self, result: Optional[dict]):
        """Read結果が変更された"""
        if result:
            # ページ情報をステータスバーに表示
            metadata = result.get("metadata", {})
            pdf_info = metadata.get("pdf", {})
            page_count = pdf_info.get("page_count", 0)
            self.statusBar().showMessage(f"ページ数: {page_count}")

        self.update_action_states()

    def on_detect_result_changed(self, result: Optional[dict]):
        """Detect結果が変更された"""
        self._refresh_result_view_from_state()

    def on_duplicate_result_changed(self, result: Optional[dict]):
        """Duplicate結果が変更された"""
        self._refresh_result_view_from_state()

    def on_status_message_changed(self, message: str):
        """ステータスメッセージが変更された"""
        self.statusBar().showMessage(message)

    def _refresh_result_view_from_state(self):
        """現在の状態から結果一覧とプレビューハイライトを再構築する"""
        current_result = self.app_state.duplicate_result or self.app_state.detect_result
        self.result_panel.load_entities(current_result)
        if current_result:
            self._highlight_all_entities(current_result)
        else:
            self._all_preview_entities = []
            self.pdf_preview.set_highlighted_entities([])
        self.update_action_states()

    # =========================================================================
    # Phase 4: 編集UIイベントハンドラ
    # =========================================================================

    def on_entity_selected(self, entities: list):
        """エンティティが選択された（選択状態を更新してプレビューを再描画）"""
        if not self._all_preview_entities:
            return

        # 選択されたエンティティを特定するためのキーセットを作成
        selected_keys = set()
        for entity in entities:
            start_pos = entity.get("start", {})
            end_pos = entity.get("end", {})
            page_num = start_pos.get("page_num", 0) if isinstance(start_pos, dict) else 0
            key = (
                entity.get("word", ""),
                entity.get("entity", ""),
                page_num,
                start_pos.get("block_num", 0) if isinstance(start_pos, dict) else 0,
                start_pos.get("offset", 0) if isinstance(start_pos, dict) else 0,
            )
            selected_keys.add(key)

        # 全エンティティの選択状態を更新
        for pe in self._all_preview_entities:
            key = (
                pe.get("text", ""),
                pe.get("entity_type", ""),
                pe.get("page_num", 0),
                pe.get("block_num", 0),
                pe.get("offset", 0),
            )
            pe["is_selected"] = key in selected_keys

        # プレビューを再描画（全エンティティを維持）
        self.pdf_preview.set_highlighted_entities(self._all_preview_entities)

        # 選択されたエンティティのページに移動
        if entities:
            start_pos = entities[0].get("start", {})
            page_num = start_pos.get("page_num", 0) if isinstance(start_pos, dict) else 0
            self.pdf_preview.go_to_page(page_num)

    def on_entity_deleted(self, index: int):
        """エンティティが削除された"""
        self.log_message(f"エンティティ #{index + 1} を削除しました")
        self._set_dirty(True)

        # AppStateの結果を更新
        self._update_app_state_from_result_panel()

        # プレビューエンティティも再構築
        current_result = (
            self.app_state.duplicate_result
            or self.app_state.detect_result
            or self.app_state.read_result
        )
        if current_result:
            self._highlight_all_entities(current_result)

    def on_entity_updated(self, index: int, entity: dict):
        """エンティティが更新された"""
        entity_type = entity.get("entity", "")
        text = entity.get("word", "")
        self.log_message(f"エンティティ #{index + 1} を更新: {text} → {entity_type}")
        self._set_dirty(True)

        # AppStateの結果を更新
        self._update_app_state_from_result_panel()

        # プレビューエンティティも再構築
        current_result = (
            self.app_state.duplicate_result
            or self.app_state.detect_result
            or self.app_state.read_result
        )
        if current_result:
            self._highlight_all_entities(current_result)

    def on_entity_added(self, entity: dict):
        """エンティティが追加された"""
        text = entity.get("word", "")
        entity_type = entity.get("entity", "")
        self.log_message(f"PII追加: {text} ({entity_type})")
        self._set_dirty(True)

        # AppStateの結果を更新
        self._update_app_state_from_result_panel()

        # プレビューを再描画
        current_result = (
            self.app_state.duplicate_result
            or self.app_state.detect_result
            or self.app_state.read_result
        )
        if current_result:
            self._highlight_all_entities(current_result)

    def on_text_selected(self, selection_data: dict):
        """PDFプレビューでテキストが選択された"""
        # エンティティタイプ選択ダイアログを表示（位置情報は選択領域から自動設定）
        self.result_panel.add_manual_entity(selection_data)

    def on_select_current_page_requested(self):
        """Ctrl+A: 表示ページの項目のみResultPanelで全選択"""
        current_page = int(getattr(self.pdf_preview, "current_page_num", 0) or 0)
        rows = []
        for i, entity in enumerate(self.result_panel.get_entities()):
            if self._entity_page_num(entity) == current_page:
                rows.append(i)
        self.result_panel.select_rows(rows)

    def on_preview_entity_clicked(self, preview_index: int):
        """PDFプレビュー上のエンティティクリック→ResultPanelの該当行を選択"""
        if preview_index < 0 or preview_index >= len(self._all_preview_entities):
            return

        clicked_entity = self._all_preview_entities[preview_index]
        clicked_text = clicked_entity.get("text", "")
        clicked_type = clicked_entity.get("entity_type", "")
        clicked_page = clicked_entity.get("page_num", 0)
        clicked_block = clicked_entity.get("block_num", 0)
        clicked_offset = clicked_entity.get("offset", 0)

        # ResultPanelのエンティティリストから一致するものを検索
        for i, entity in enumerate(self.result_panel.entities):
            start_pos = entity.get("start", {})
            page_num = start_pos.get("page_num", 0) if isinstance(start_pos, dict) else 0
            block_num = start_pos.get("block_num", 0) if isinstance(start_pos, dict) else 0
            offset = start_pos.get("offset", 0) if isinstance(start_pos, dict) else 0
            if (entity.get("word", "") == clicked_text
                    and entity.get("entity", "") == clicked_type
                    and page_num == clicked_page
                    and block_num == clicked_block
                    and offset == clicked_offset):
                self.result_panel.select_row(i)
                return

    def _highlight_all_entities(self, result: dict):
        """全エンティティのハイライトをPDFプレビューに表示"""
        detect_list = result.get("detect", [])
        if not detect_list:
            self._all_preview_entities = []
            self.pdf_preview.set_highlighted_entities([])
            return

        # 座標マップを取得
        offset2coords = self._get_offset2coords_map()

        # CLI形式からプレビュー用に変換して全て保持
        self._all_preview_entities = []
        for entity in detect_list:
            start_pos = entity.get("start", {})
            end_pos = entity.get("end", {})
            page_num = start_pos.get("page_num", 0) if isinstance(start_pos, dict) else 0
            selection_mode = entity.get("selection_mode", "")
            mask_circles_pdf = entity.get("mask_circles_pdf")

            # rects_pdf（行ごとの矩形リスト）を座標マップから解決
            rects_pdf = entity.get("rects_pdf")
            if not rects_pdf and offset2coords and isinstance(start_pos, dict) and isinstance(end_pos, dict):
                rects_pdf = self._resolve_rects_from_offset_map(
                    start_pos, end_pos, offset2coords
                )

            preview_entity = {
                "page_num": page_num,
                "page": page_num,
                "entity_type": entity.get("entity", ""),
                "text": entity.get("word", ""),
                "rects_pdf": rects_pdf,
                "mask_circles_pdf": mask_circles_pdf,
                "selection_mode": selection_mode,
                "is_selected": False,
                "block_num": start_pos.get("block_num", 0) if isinstance(start_pos, dict) else 0,
                "offset": start_pos.get("offset", 0) if isinstance(start_pos, dict) else 0,
            }
            self._all_preview_entities.append(preview_entity)

        # プレビューにハイライト設定
        self.pdf_preview.set_highlighted_entities(self._all_preview_entities)

    def _get_offset2coords_map(self) -> dict:
        """現在のresultからoffset2coordsMapを取得"""
        for result in [
            self.app_state.duplicate_result,
            self.app_state.detect_result,
            self.app_state.read_result,
        ]:
            if result and "offset2coordsMap" in result:
                return result["offset2coordsMap"]
        return {}

    def _resolve_rects_from_offset_map(
        self,
        start_pos: dict,
        end_pos: dict,
        offset2coords: dict,
    ) -> Optional[List[list]]:
        """offset2coordsMapからエンティティの行ごとの矩形リストを計算する"""
        try:
            def _group_rects_by_line(bboxes: List[list]) -> List[list]:
                """同一ブロック内の文字bboxを行単位でまとめる。"""
                if not bboxes:
                    return []

                items = []
                for bbox in bboxes:
                    try:
                        x0, y0, x1, y1 = map(float, bbox[:4])
                    except Exception:
                        continue
                    if x1 <= x0 or y1 <= y0:
                        continue
                    cy = (y0 + y1) / 2.0
                    h = y1 - y0
                    items.append((cy, h, [x0, y0, x1, y1]))

                if not items:
                    return []

                items.sort(key=lambda t: t[0])
                heights = sorted(item[1] for item in items)
                median_h = heights[len(heights) // 2]
                y_threshold = max(1.5, median_h * 0.6)

                grouped = []
                for cy, _, rect in items:
                    if not grouped:
                        grouped.append({"sum_cy": cy, "count": 1, "rects": [rect]})
                        continue

                    last = grouped[-1]
                    group_cy = last["sum_cy"] / last["count"]
                    if abs(cy - group_cy) <= y_threshold:
                        last["rects"].append(rect)
                        last["sum_cy"] += cy
                        last["count"] += 1
                    else:
                        grouped.append({"sum_cy": cy, "count": 1, "rects": [rect]})

                line_rects = []
                for grp in grouped:
                    rects = grp["rects"]
                    line_rects.append(
                        [
                            min(r[0] for r in rects),
                            min(r[1] for r in rects),
                            max(r[2] for r in rects),
                            max(r[3] for r in rects),
                        ]
                    )
                return line_rects

            ps = int(start_pos.get("page_num", 0))
            pe = int(end_pos.get("page_num", ps))
            bs = int(start_pos.get("block_num", 0))
            be = int(end_pos.get("block_num", bs))
            os_ = int(start_pos.get("offset", 0))
            oe = int(end_pos.get("offset", 0))

            # ブロックごとにbboxを収集（同一ブロック内は後段で行単位に分割）
            block_bboxes: Dict[tuple, list] = {}  # (page, block) → [bbox, ...]
            for p in range(ps, pe + 1):
                page_dict = offset2coords.get(str(p), {})
                if not isinstance(page_dict, dict):
                    continue
                block_ids = sorted(int(k) for k in page_dict.keys() if str(k).isdigit())
                b_start = bs if p == ps else (block_ids[0] if block_ids else 0)
                b_end = be if p == pe else (block_ids[-1] if block_ids else 0)
                for b in block_ids:
                    if b < b_start or b > b_end:
                        continue
                    block_list = page_dict.get(str(b), [])
                    if not isinstance(block_list, list):
                        continue
                    o_start = os_ if (p == ps and b == bs) else 0
                    o_end = oe if (p == pe and b == be) else (len(block_list) - 1)
                    for off in range(o_start, min(o_end + 1, len(block_list))):
                        bbox = block_list[off]
                        if isinstance(bbox, list) and len(bbox) >= 4:
                            key = (p, b)
                            if key not in block_bboxes:
                                block_bboxes[key] = []
                            block_bboxes[key].append(bbox[:4])

            if not block_bboxes:
                return None

            # 各ブロック内のbboxを行単位にまとめ、行ごとの外接矩形を返す
            rects = []
            for key in sorted(block_bboxes.keys()):
                bboxes = block_bboxes[key]
                rects.extend(_group_rects_by_line(bboxes))

            return rects if rects else None
        except Exception as e:
            logger.warning(f"座標解決に失敗: {e}")
            return None

    def _update_app_state_from_result_panel(self):
        """ResultPanelの内容でAppStateを更新"""
        entities = self.result_panel.get_entities()
        if not isinstance(entities, list):
            entities = []
        updated_detect = copy.deepcopy(entities)

        # duplicate結果がある場合はそちらを優先
        if self.app_state.has_duplicate_result():
            result = copy.deepcopy(self.app_state.duplicate_result or {})
            result["detect"] = updated_detect
            self.app_state.duplicate_result = result
        elif self.app_state.has_detect_result():
            result = copy.deepcopy(self.app_state.detect_result or {})
            result["detect"] = updated_detect
            self.app_state.detect_result = result
        elif self.app_state.has_read_result():
            # Detect前の手動マークもread_resultへ保持して即時反映する
            result = copy.deepcopy(self.app_state.read_result or {})
            result["detect"] = updated_detect
            self.app_state.read_result = result

    def _get_current_result(self) -> Optional[dict]:
        """表示・ハイライト基準となる現在の結果を返す"""
        if isinstance(self.app_state.duplicate_result, dict):
            return self.app_state.duplicate_result
        if isinstance(self.app_state.detect_result, dict):
            return self.app_state.detect_result
        if isinstance(self.app_state.read_result, dict):
            return self.app_state.read_result
        return None

    def _get_export_source_result(self) -> Optional[dict]:
        """エクスポート用に使用する結果（duplicate優先）を返す"""
        if isinstance(self.app_state.duplicate_result, dict):
            return self.app_state.duplicate_result
        if isinstance(self.app_state.detect_result, dict):
            return self.app_state.detect_result
        return None

    def _sync_all_result_states_from_entities(self, entities: List[Dict[str, Any]]) -> None:
        """ResultPanelの検出項目をAppStateの全結果へ同期"""
        normalized_entities = [copy.deepcopy(entity) for entity in entities if isinstance(entity, dict)]

        if isinstance(self.app_state.read_result, dict):
            read_result = copy.deepcopy(self.app_state.read_result)
            read_result["detect"] = copy.deepcopy(normalized_entities)
            self.app_state.read_result = read_result

        if isinstance(self.app_state.detect_result, dict):
            detect_result = copy.deepcopy(self.app_state.detect_result)
            detect_result["detect"] = copy.deepcopy(normalized_entities)
            self.app_state.detect_result = detect_result

        if isinstance(self.app_state.duplicate_result, dict):
            duplicate_result = copy.deepcopy(self.app_state.duplicate_result)
            duplicate_result["detect"] = copy.deepcopy(normalized_entities)
            self.app_state.duplicate_result = duplicate_result

    def _select_export_dpi(self) -> Optional[int]:
        """画像出力時のDPIを選択"""
        options = ["72", "150", "300", "600"]
        selected, ok = QInputDialog.getItem(
            self,
            "DPI選択",
            "画像出力DPI:",
            options,
            2,
            False,
        )
        if not ok:
            return None
        try:
            dpi = int(selected)
        except (TypeError, ValueError):
            QMessageBox.warning(self, "警告", "無効なDPIです")
            return None
        if dpi <= 0:
            QMessageBox.warning(self, "警告", "DPIは1以上を指定してください")
            return None
        return dpi

    def _select_output_pdf_path(self, title: str, stem_suffix: str) -> Optional[Path]:
        """保存先PDFパスを選択"""
        default_path = self.app_state.pdf_path.with_stem(
            self.app_state.pdf_path.stem + stem_suffix
        )
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            title,
            str(default_path),
            "PDF Files (*.pdf);;All Files (*)",
        )
        if not output_path:
            return None
        output_pdf = Path(output_path)
        if output_pdf.suffix.lower() != ".pdf":
            output_pdf = output_pdf.with_suffix(".pdf")
        return output_pdf

    @staticmethod
    def _is_manual_entity(entity: Any) -> bool:
        """手動マークの判定"""
        if not isinstance(entity, dict):
            return False
        if entity.get("manual") is True:
            return True
        return str(entity.get("origin", "")).lower() == "manual"

    @staticmethod
    def _entity_identity_key(entity: Dict[str, Any]) -> tuple:
        """検出項目の同一性判定キー"""
        start_pos = entity.get("start", {})
        end_pos = entity.get("end", {})
        if not isinstance(start_pos, dict):
            start_pos = {}
        if not isinstance(end_pos, dict):
            end_pos = {}

        return (
            str(entity.get("word", "")),
            str(entity.get("entity", "")),
            int(start_pos.get("page_num", -1) or -1),
            int(start_pos.get("block_num", -1) or -1),
            int(start_pos.get("offset", -1) or -1),
            int(end_pos.get("page_num", -1) or -1),
            int(end_pos.get("block_num", -1) or -1),
            int(end_pos.get("offset", -1) or -1),
        )

    @staticmethod
    def _entity_page_num(entity: Dict[str, Any]) -> int:
        """検出項目の開始ページ番号（0始まり）を取得"""
        start_pos = entity.get("start", {})
        if not isinstance(start_pos, dict):
            return -1
        try:
            return int(start_pos.get("page_num", -1))
        except (TypeError, ValueError):
            return -1

    def _merge_detect_result_for_scope(self, detect_result: Dict[str, Any]) -> Dict[str, Any]:
        """表示ページ検出時は対象ページのみ差し替え、他ページは維持する"""
        if self._detect_scope != "current_page":
            return detect_result
        if not self._detect_target_pages:
            return detect_result
        if not isinstance(self._detect_base_result, dict):
            return detect_result

        target_pages = set(self._detect_target_pages)
        base_detect = self._detect_base_result.get("detect", [])
        new_detect = detect_result.get("detect", [])

        if not isinstance(base_detect, list):
            base_detect = []
        if not isinstance(new_detect, list):
            new_detect = []

        merged_detect = [
            entity
            for entity in base_detect
            if self._entity_page_num(entity) not in target_pages
        ]
        merged_detect.extend(
            entity
            for entity in new_detect
            if self._entity_page_num(entity) in target_pages
        )

        merged_result = copy.deepcopy(detect_result)
        merged_result["detect"] = merged_detect
        return merged_result

    def _reset_detect_scope_context(self):
        """Detectスコープ管理の一時状態をクリア"""
        self._detect_scope = "all"
        self._detect_target_pages = None
        self._detect_base_result = None

    def _merge_duplicate_result_for_scope(self, duplicate_result: Dict[str, Any]) -> Dict[str, Any]:
        """表示ページ重複削除時は対象ページのみ差し替え、他ページは維持する"""
        if self._duplicate_scope != "current_page":
            return duplicate_result
        if not self._duplicate_target_pages:
            return duplicate_result
        if not isinstance(self._duplicate_base_result, dict):
            return duplicate_result

        target_pages = set(self._duplicate_target_pages)
        base_detect = self._duplicate_base_result.get("detect", [])
        new_detect = duplicate_result.get("detect", [])

        if not isinstance(base_detect, list):
            base_detect = []
        if not isinstance(new_detect, list):
            new_detect = []

        merged_detect = [
            entity
            for entity in base_detect
            if self._entity_page_num(entity) not in target_pages
        ]
        merged_detect.extend(
            entity
            for entity in new_detect
            if self._entity_page_num(entity) in target_pages
        )

        merged_result = copy.deepcopy(duplicate_result)
        merged_result["detect"] = merged_detect
        return merged_result

    def _reset_duplicate_scope_context(self):
        """Duplicateスコープ管理の一時状態をクリア"""
        self._duplicate_scope = "all"
        self._duplicate_target_pages = None
        self._duplicate_base_result = None

    def _build_read_result_for_detect(self) -> Dict[str, Any]:
        """Detect入力用にread_resultへ手動マークを統合したコピーを返す"""
        base_read = self.app_state.read_result or {}
        if not isinstance(base_read, dict):
            return {}

        read_input = copy.deepcopy(base_read)
        read_detect = read_input.get("detect", [])
        if not isinstance(read_detect, list):
            read_detect = []

        # ResultPanelに表示中の手動マークだけを保持対象として抽出
        current_entities = self.result_panel.get_entities()
        manual_entities = []
        if isinstance(current_entities, list):
            for entity in current_entities:
                if self._is_manual_entity(entity):
                    manual_entities.append(copy.deepcopy(entity))

        if not manual_entities:
            read_input["detect"] = read_detect
            return read_input

        merged_detect = []
        seen = set()

        for entity in read_detect:
            if not isinstance(entity, dict):
                continue
            key = self._entity_identity_key(entity)
            if key in seen:
                continue
            seen.add(key)
            merged_detect.append(entity)

        added_count = 0
        for entity in manual_entities:
            key = self._entity_identity_key(entity)
            if key in seen:
                continue
            seen.add(key)
            merged_detect.append(entity)
            added_count += 1

        if added_count > 0:
            self.log_message(f"手動マーク {added_count}件を保持してDetectを実行します")

        read_input["detect"] = merged_detect
        return read_input

    # =========================================================================
    # ユーティリティ
    # =========================================================================

    def _retarget_result_pdf_path(self, result: Optional[dict], pdf_path: Path) -> Optional[dict]:
        """結果JSON内のmetadata.pdf.pathを保存先PDFに付け替える"""
        if not isinstance(result, dict):
            return result
        out = copy.deepcopy(result)
        metadata = out.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            out["metadata"] = metadata
        pdf_meta = metadata.setdefault("pdf", {})
        if not isinstance(pdf_meta, dict):
            pdf_meta = {}
            metadata["pdf"] = pdf_meta
        pdf_meta["path"] = str(pdf_path.resolve())
        return out

    def _build_mapping_payload(self, saved_pdf_path: Path) -> dict:
        """現在の状態から保存用マッピングJSONを構築"""
        read_result = self._retarget_result_pdf_path(self.app_state.read_result, saved_pdf_path)
        detect_result = self._retarget_result_pdf_path(self.app_state.detect_result, saved_pdf_path)
        duplicate_result = self._retarget_result_pdf_path(self.app_state.duplicate_result, saved_pdf_path)

        return {
            "pdf_path": str(saved_pdf_path.resolve()),
            "read_result": read_result,
            "detect_result": detect_result,
            "duplicate_result": duplicate_result,
        }

    def _embed_mapping_into_pdf(self, pdf_path: Path, payload: dict) -> bool:
        """マッピングJSONをPDF埋め込みファイルとして保存"""
        temp_path = pdf_path.with_suffix(pdf_path.suffix + ".tmp")
        try:
            json_data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            with fitz.open(str(pdf_path)) as doc:
                embedded_files = doc.embfile_names()
                if self.EMBEDDED_MAPPING_FILENAME in embedded_files:
                    doc.embfile_del(self.EMBEDDED_MAPPING_FILENAME)
                doc.embfile_add(
                    self.EMBEDDED_MAPPING_FILENAME,
                    json_data,
                    filename=self.EMBEDDED_MAPPING_FILENAME,
                )
                doc.save(str(temp_path), garbage=4, deflate=True, clean=True)

            temp_path.replace(pdf_path)
            return True
        except Exception as e:
            self.log_message(f"マッピング埋め込みに失敗: {e}")
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            return False

    def _load_mapping_for_pdf(self, pdf_path: Path) -> bool:
        """マッピングを読み込んで状態を復元（サイドカー優先、PDF埋め込みは後方互換）"""
        # (1) サイドカーファイルを優先
        sidecar = self._sidecar_path_for(pdf_path)
        if sidecar.exists():
            try:
                payload = json.loads(sidecar.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    # ハッシュ照合
                    stored_hash = payload.get("content_hash", "")
                    if stored_hash:
                        from src.cli.common import sha256_pdf_content
                        current_hash = sha256_pdf_content(str(pdf_path))
                        if current_hash != stored_hash:
                            reply = QMessageBox.question(
                                self,
                                "ハッシュ不一致",
                                "PDFの内容がサイドカーマッピング保存時と異なります。\n"
                                "マッピングを読み込みますか？",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.Yes,
                            )
                            if reply != QMessageBox.StandardButton.Yes:
                                return False

                    if self._restore_mapping_from_payload(payload, pdf_path):
                        self.log_message(f"サイドカーマッピングを読み込みました: {sidecar}")
                        return True
            except Exception as e:
                self.log_message(f"サイドカーマッピング読込に失敗: {sidecar} ({e})")

        # (2) PDF埋め込み（後方互換）
        try:
            with fitz.open(str(pdf_path)) as doc:
                embedded_files = doc.embfile_names()
                if self.EMBEDDED_MAPPING_FILENAME not in embedded_files:
                    return False
                payload_raw = doc.embfile_get(self.EMBEDDED_MAPPING_FILENAME)

            payload = json.loads(payload_raw.decode("utf-8"))
            if not isinstance(payload, dict):
                return False

            if self._restore_mapping_from_payload(payload, pdf_path):
                self.log_message("PDF埋め込みマッピングを読み込みました（後方互換）")
                return True
            return False
        except Exception as e:
            self.log_message(f"埋め込みマッピング読込に失敗: {pdf_path} ({e})")
            return False

    def _restore_mapping_from_payload(self, payload: dict, pdf_path: Path) -> bool:
        """マッピングペイロードからAppStateを復元する共通ロジック"""
        if not isinstance(payload, dict):
            return False

        if any(k in payload for k in ["read_result", "detect_result", "duplicate_result"]):
            read_result = payload.get("read_result")
            detect_result = payload.get("detect_result")
            duplicate_result = payload.get("duplicate_result")
        else:
            # 互換: 旧フォーマット（単一結果JSON）
            read_result = payload
            detect_result = payload if payload.get("detect") else None
            duplicate_result = None

        self.app_state.read_result = self._retarget_result_pdf_path(read_result, pdf_path)
        self.app_state.detect_result = self._retarget_result_pdf_path(detect_result, pdf_path)
        self.app_state.duplicate_result = self._retarget_result_pdf_path(duplicate_result, pdf_path)
        return True

    def log_message(self, message: str):
        """ログメッセージを追加"""
        # 初期化中はlog_textがまだ存在しない可能性がある
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.append(message)

    def update_action_states(self):
        """各アクションの有効/無効状態を更新"""
        has_pdf = self.app_state.has_pdf()
        has_read = self.app_state.has_read_result()
        has_detect = self.app_state.has_detect_result()
        has_export_source = self._get_export_source_result() is not None
        has_current_result = self._get_current_result() is not None
        is_running = self.task_runner.is_running()

        # Read: PDFが選択されていて、タスクが実行中でなければ有効
        self.read_action.setEnabled(has_pdf and not is_running)

        # ファイルを閉じる: PDFが選択されていて、タスクが実行中でなければ有効
        self.close_pdf_action.setEnabled(has_pdf and not is_running)

        # 設定: タスク実行中は無効
        self.config_action.setEnabled(not is_running)

        # Detect: Read結果があって、タスクが実行中でなければ有効
        detect_enabled = has_read and not is_running
        self.detect_button.setEnabled(detect_enabled)
        self.detect_all_action.setEnabled(detect_enabled)
        self.detect_current_action.setEnabled(detect_enabled and has_pdf)

        # 対象削除: 現在表示中の結果があり、タスクが実行中でなければ有効
        target_delete_enabled = has_current_result and not is_running
        self.target_delete_button.setEnabled(target_delete_enabled)
        self.target_delete_current_action.setEnabled(target_delete_enabled and has_pdf)
        self.target_delete_all_action.setEnabled(target_delete_enabled)

        # 重複削除: Detect結果があり、タスクが実行中でなければ有効
        duplicate_enabled = has_detect and not is_running
        self.duplicate_button.setEnabled(duplicate_enabled)
        self.duplicate_current_action.setEnabled(duplicate_enabled and has_pdf)
        self.duplicate_all_action.setEnabled(duplicate_enabled)

        # Export: Detect/Duplicate結果があり、タスクが実行中でなければ有効
        export_enabled = has_pdf and has_export_source and not is_running
        self.export_button.setEnabled(export_enabled)
        self.export_annotations_action.setEnabled(export_enabled)
        self.export_mask_action.setEnabled(export_enabled)
        self.export_mask_as_image_action.setEnabled(export_enabled)
        self.export_marked_as_image_action.setEnabled(export_enabled)

        # Save: PDF + Read結果があり、タスクが実行中でなければ有効
        self.save_action.setEnabled(has_pdf and has_read and not is_running)

    # =========================================================================
    # TaskRunnerシグナルハンドラ（Phase 2）
    # =========================================================================

    def on_task_started(self):
        """タスク開始時"""
        self.app_state.status_message = "処理を実行中..."
        self.update_action_states()

    def on_task_running_state_changed(self, _: bool):
        """TaskRunnerの実行状態が変化した"""
        self.update_action_states()

    def on_task_progress(self, percent: int, message: str):
        """タスク進捗更新時"""
        self.log_message(f"[{percent}%] {message}")
        self.app_state.status_message = f"処理中: {message}"

    def on_task_finished(self, result):
        """タスク完了時"""
        if self.current_task == "read":
            self.app_state.read_result = result
            self.log_message("Read処理が完了しました")
            self._set_dirty(True)
        elif self.current_task == "detect":
            detect_result = result if isinstance(result, dict) else {}
            detect_result = self._merge_detect_result_for_scope(detect_result)
            self.app_state.detect_result = detect_result
            self.app_state.duplicate_result = None
            detect_count = len(detect_result.get("detect", []))
            if self._detect_scope == "current_page" and self._detect_target_pages:
                page_num = self._detect_target_pages[0] + 1
                self.log_message(
                    f"Detect処理が完了しました（表示ページ {page_num} のみ更新, {detect_count}件）"
                )
            else:
                self.log_message(f"Detect処理が完了しました（{detect_count}件）")
            self._reset_detect_scope_context()
            self._set_dirty(True)
        elif self.current_task == "duplicate":
            duplicate_result = result if isinstance(result, dict) else {}
            duplicate_result = self._merge_duplicate_result_for_scope(duplicate_result)
            self.app_state.duplicate_result = duplicate_result
            detect_count = len(duplicate_result.get("detect", []))
            if self._duplicate_scope == "current_page" and self._duplicate_target_pages:
                page_num = self._duplicate_target_pages[0] + 1
                self.log_message(
                    f"Duplicate処理が完了しました（表示ページ {page_num} のみ更新, {detect_count}件）"
                )
            else:
                self.log_message(f"Duplicate処理が完了しました（{detect_count}件）")
            self._reset_duplicate_scope_context()
            self._set_dirty(True)
        elif self.current_task == "mask":
            result_dict = result if isinstance(result, dict) else {}
            output_path = result_dict.get("output_path", "")
            entity_count = result_dict.get("entity_count", 0)
            self.log_message(f"Mask処理が完了しました（{entity_count}件）")
            self.log_message(f"保存先: {output_path}")
            self.statusBar().showMessage("マスキング済みPDFを保存しました")
            self._set_dirty(True)
        elif self.current_task == "export_annotations":
            result_dict = result if isinstance(result, dict) else {}
            output_path = result_dict.get("output_path", "")
            annotation_count = result_dict.get("annotation_count", 0)
            self.log_message(f"アノテーション付きエクスポート完了（{annotation_count}件）")
            self.log_message(f"保存先: {output_path}")
            self.statusBar().showMessage("注釈付きPDFを保存しました")
            self._set_dirty(True)
        elif self.current_task == "mask_as_image":
            result_dict = result if isinstance(result, dict) else {}
            output_path = result_dict.get("output_path", "")
            entity_count = result_dict.get("entity_count", 0)
            self.log_message(f"マスク（画像として保存）が完了しました（{entity_count}件）")
            self.log_message(f"保存先: {output_path}")
            self.statusBar().showMessage("マスク画像PDFを保存しました")
            self._set_dirty(True)
        elif self.current_task == "marked_as_image":
            result_dict = result if isinstance(result, dict) else {}
            output_path = result_dict.get("output_path", "")
            entity_count = result_dict.get("entity_count", 0)
            self.log_message(f"マーク（画像として保存）が完了しました（{entity_count}件）")
            self.log_message(f"保存先: {output_path}")
            self.statusBar().showMessage("マーク画像PDFを保存しました")
            self._set_dirty(True)
        else:
            self.log_message(f"タスク '{self.current_task}' が完了しました")

        self.current_task = None
        self.update_action_states()

    def on_task_error(self, error_msg: str):
        """タスクエラー時"""
        self.log_message(f"エラー: {error_msg}")
        QMessageBox.critical(self, "エラー", error_msg)
        self.app_state.status_message = "エラーが発生しました"
        if self.current_task == "detect":
            self._reset_detect_scope_context()
        if self.current_task == "duplicate":
            self._reset_duplicate_scope_context()
        self.current_task = None
        self.update_action_states()
