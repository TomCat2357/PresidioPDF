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
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

logger = logging.getLogger(__name__)

from ..models.app_state import AppState
from ..controllers.task_runner import TaskRunner
from ..services.pipeline_service import PipelineService
from .pdf_preview import PDFPreviewWidget
from .result_panel import ResultPanel


class MainWindow(QMainWindow):
    """メインウィンドウクラス"""

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state

        # Phase 2: TaskRunnerの初期化
        self.task_runner = TaskRunner(self)
        self.current_task = None  # 現在実行中のタスク名

        # 全プレビューエンティティを保持（選択状態管理用）
        self._all_preview_entities: List[Dict] = []

        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        """UIの初期化"""
        # ウィンドウの基本設定
        self.setWindowTitle("PresidioPDF - PyQt版 (Phase 4)")
        self.setGeometry(100, 100, 1400, 900)

        # ツールバーの作成
        self.create_toolbar()

        # 中央ウィジェットの作成
        self.create_central_widget()

        # ステータスバーの作成
        self.create_statusbar()

    def create_toolbar(self):
        """ツールバーの作成"""
        toolbar = QToolBar("メインツールバー")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # アクションの定義

        # PDFファイルを開く（Read自動実行）
        open_action = QAction("📂 PDF選択", self)
        open_action.setStatusTip("PDFファイルを選択して読み込み")
        open_action.triggered.connect(self.on_open_pdf)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        # Read（内部的に保持、ツールバーには非表示）
        read_action = QAction("📖 Read", self)
        read_action.triggered.connect(self.on_read)
        self.read_action = read_action

        # Detect（PII検出）
        detect_action = QAction("🔍 Detect", self)
        detect_action.setStatusTip("個人情報（PII）を検出")
        detect_action.triggered.connect(self.on_detect)
        toolbar.addAction(detect_action)
        self.detect_action = detect_action

        # Duplicate（重複処理）
        duplicate_action = QAction("🔄 Duplicate", self)
        duplicate_action.setStatusTip("重複する検出結果を処理")
        duplicate_action.triggered.connect(self.on_duplicate)
        toolbar.addAction(duplicate_action)
        self.duplicate_action = duplicate_action

        # Mask（マスキング）
        mask_action = QAction("🎭 Mask", self)
        mask_action.setStatusTip("検出結果をマスキング")
        mask_action.triggered.connect(self.on_mask)
        toolbar.addAction(mask_action)
        self.mask_action = mask_action

        toolbar.addSeparator()

        # Export（エクスポート）
        export_action = QAction("💾 Export", self)
        export_action.setStatusTip("処理結果をエクスポート")
        export_action.triggered.connect(self.on_export)
        toolbar.addAction(export_action)
        self.export_action = export_action

        # 初期状態では一部のアクションを無効化
        self.update_action_states()

    def create_central_widget(self):
        """中央ウィジェットの作成（Phase 4: 3分割レイアウト）"""
        # メイン水平スプリッター（3分割: PDF情報、プレビュー、検出結果）
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左側パネル: PDF情報・ページ一覧
        left_panel = self.create_left_panel()
        main_splitter.addWidget(left_panel)

        # 中央パネル: PDFプレビュー（Phase 4）
        self.pdf_preview = PDFPreviewWidget()
        main_splitter.addWidget(self.pdf_preview)

        # 右側パネル: 検出結果一覧（Phase 4: 編集機能付き）
        self.result_panel = ResultPanel()
        main_splitter.addWidget(self.result_panel)

        # 分割比率（左:中央:右 = 1:2:2）
        main_splitter.setSizes([300, 550, 550])

        # 全体の縦分割（メイン領域 + ログ領域）
        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.addWidget(main_splitter)

        # ログ領域
        log_panel = self.create_log_panel()
        vertical_splitter.addWidget(log_panel)

        # 分割比率（メイン:ログ = 5:1）
        vertical_splitter.setSizes([750, 150])

        self.setCentralWidget(vertical_splitter)

    def create_left_panel(self) -> QWidget:
        """左側パネル: PDF情報・ページ一覧"""
        panel = QWidget()
        layout = QVBoxLayout()

        # PDFファイル情報
        self.pdf_info_label = QLabel("PDFファイル: （未選択）")
        self.pdf_info_label.setStyleSheet("padding: 5px; background-color: #f0f0f0;")
        layout.addWidget(self.pdf_info_label)

        # ページ一覧（将来の拡張用）
        pages_label = QLabel("ページ一覧:")
        layout.addWidget(pages_label)

        self.pages_text = QTextEdit()
        self.pages_text.setReadOnly(True)
        self.pages_text.setPlaceholderText("PDFを読み込むとページ情報が表示されます")
        layout.addWidget(self.pages_text)

        panel.setLayout(layout)
        return panel

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

        # PDFプレビューからの逆方向連携
        self.pdf_preview.entity_clicked.connect(self.on_preview_entity_clicked)

    # =========================================================================
    # アクションハンドラー（Phase 1: スタブ実装）
    # =========================================================================

    def on_open_pdf(self):
        """PDFファイルを開く（Read処理も自動実行）"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "PDFファイルを選択",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            self.app_state.pdf_path = Path(file_path)
            self.log_message(f"PDFファイルを選択: {file_path}")
            self.update_action_states()
            # Read処理を自動実行
            self._auto_read()

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

    def on_detect(self):
        """Detect処理（Phase 2: 非同期実行）"""
        if not self.app_state.has_read_result():
            QMessageBox.warning(self, "警告", "Read処理が完了していません")
            return

        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        self.log_message("Detect処理を開始...")

        # TaskRunnerで非同期実行
        self.current_task = "detect"
        self.task_runner.start_task(
            PipelineService.run_detect,
            self.app_state.read_result
        )

    def on_duplicate(self):
        """Duplicate処理（Phase 3: 非同期実行）"""
        if not self.app_state.has_detect_result():
            QMessageBox.warning(self, "警告", "Detect処理が完了していません")
            return

        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        self.log_message("Duplicate処理を開始...")

        # TaskRunnerで非同期実行
        self.current_task = "duplicate"
        self.task_runner.start_task(
            PipelineService.run_duplicate,
            self.app_state.detect_result
        )

    def on_mask(self):
        """Mask処理（Phase 3: 非同期実行）"""
        # Duplicate結果があればそれを使い、なければDetect結果を使う
        detect_or_dup_result = self.app_state.duplicate_result or self.app_state.detect_result

        if not detect_or_dup_result:
            QMessageBox.warning(self, "警告", "Detect処理が完了していません")
            return

        if not self.app_state.has_pdf():
            QMessageBox.warning(self, "警告", "PDFファイルが選択されていません")
            return

        if self.task_runner.is_running():
            QMessageBox.warning(self, "警告", "別のタスクが実行中です")
            return

        # 出力先の選択
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "マスキング結果の保存先",
            str(self.app_state.pdf_path.with_stem(self.app_state.pdf_path.stem + "_masked")),
            "PDF Files (*.pdf);;All Files (*)"
        )

        if not output_path:
            return

        self.log_message("Mask処理を開始...")

        # TaskRunnerで非同期実行
        self.current_task = "mask"
        self.task_runner.start_task(
            PipelineService.run_mask,
            detect_or_dup_result,
            self.app_state.pdf_path,
            Path(output_path)
        )

    def on_export(self):
        """Export処理（Phase 1: スタブ）"""
        self.log_message("Export処理を開始（Phase 3で実装予定）...")
        # Phase 3で実装

    # =========================================================================
    # シグナルスロット
    # =========================================================================

    def on_pdf_path_changed(self, pdf_path: Optional[Path]):
        """PDFパスが変更された"""
        if pdf_path:
            self.pdf_info_label.setText(f"PDFファイル: {pdf_path.name}")
            # Phase 4: PDFプレビューに読み込み
            self.pdf_preview.load_pdf(str(pdf_path))
        else:
            self.pdf_info_label.setText("PDFファイル: （未選択）")
            self.pdf_preview.close_pdf()

    def on_read_result_changed(self, result: Optional[dict]):
        """Read結果が変更された"""
        if result:
            # ページ情報を表示（Phase 2以降で詳細実装）
            metadata = result.get("metadata", {})
            pdf_info = metadata.get("pdf", {})
            page_count = pdf_info.get("page_count", 0)
            self.pages_text.setText(f"ページ数: {page_count}")

            self.update_action_states()

    def on_detect_result_changed(self, result: Optional[dict]):
        """Detect結果が変更された"""
        if result:
            # ResultPanelに検出結果を読み込み
            self.result_panel.load_entities(result)
            # 全エンティティをハイライト表示
            self._highlight_all_entities(result)
            self.update_action_states()

    def on_duplicate_result_changed(self, result: Optional[dict]):
        """Duplicate結果が変更された"""
        if result:
            # ResultPanelに重複処理後の結果を読み込み
            self.result_panel.load_entities(result)
            # 全エンティティをハイライト表示
            self._highlight_all_entities(result)
            self.update_action_states()

    def on_status_message_changed(self, message: str):
        """ステータスメッセージが変更された"""
        self.statusBar().showMessage(message)

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
        self.log_message(f"エンティティ #{index} を削除しました")

        # AppStateの結果を更新
        self._update_app_state_from_result_panel()

        # プレビューエンティティも再構築
        current_result = self.app_state.duplicate_result or self.app_state.detect_result
        if current_result:
            self._highlight_all_entities(current_result)

    def on_entity_updated(self, index: int, entity: dict):
        """エンティティが更新された"""
        entity_type = entity.get("entity", "")
        text = entity.get("word", "")
        self.log_message(f"エンティティ #{index} を更新: {text} → {entity_type}")

        # AppStateの結果を更新
        self._update_app_state_from_result_panel()

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

            # rects_pdf（行ごとの矩形リスト）を座標マップから解決
            rects_pdf = entity.get("rects_pdf")
            if not rects_pdf and offset2coords and isinstance(start_pos, dict) and isinstance(end_pos, dict):
                rects_pdf = self._resolve_rects_from_offset_map(
                    start_pos, end_pos, offset2coords
                )

            # 後方互換: rect_pdfも保持
            rect_pdf = entity.get("rect_pdf")
            if not rect_pdf and rects_pdf:
                # 全rects_pdfの外接矩形をrect_pdfとして保持（ヒットテスト用）
                x0 = min(r[0] for r in rects_pdf)
                y0 = min(r[1] for r in rects_pdf)
                x1 = max(r[2] for r in rects_pdf)
                y1 = max(r[3] for r in rects_pdf)
                rect_pdf = [x0, y0, x1, y1]

            preview_entity = {
                "page_num": page_num,
                "page": page_num,
                "entity_type": entity.get("entity", ""),
                "text": entity.get("word", ""),
                "rect_pdf": rect_pdf,
                "rects_pdf": rects_pdf,
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

        # duplicate結果がある場合はそちらを優先
        if self.app_state.has_duplicate_result():
            result = self.app_state.duplicate_result.copy()
            result["detect"] = entities
            self.app_state.duplicate_result = result
        elif self.app_state.has_detect_result():
            result = self.app_state.detect_result.copy()
            result["detect"] = entities
            self.app_state.detect_result = result

    # =========================================================================
    # ユーティリティ
    # =========================================================================

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
        is_running = self.task_runner.is_running()

        # Read: PDFが選択されていて、タスクが実行中でなければ有効
        self.read_action.setEnabled(has_pdf and not is_running)

        # Detect: Read結果があって、タスクが実行中でなければ有効
        self.detect_action.setEnabled(has_read and not is_running)

        # Duplicate/Mask: Detect結果があって、タスクが実行中でなければ有効
        self.duplicate_action.setEnabled(has_detect and not is_running)
        self.mask_action.setEnabled(has_detect and not is_running)

        # Export: タスクが実行中でなければ有効
        self.export_action.setEnabled(not is_running)

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
        elif self.current_task == "detect":
            self.app_state.detect_result = result
            self.log_message("Detect処理が完了しました")
        elif self.current_task == "duplicate":
            self.app_state.duplicate_result = result
            detect_count = len(result.get("detect", []))
            self.log_message(f"Duplicate処理が完了しました（{detect_count}件）")
        elif self.current_task == "mask":
            output_path = result.get("output_path", "")
            entity_count = result.get("entity_count", 0)
            self.log_message(f"Mask処理が完了しました（{entity_count}件）")
            self.log_message(f"保存先: {output_path}")
            QMessageBox.information(self, "完了", f"マスキング済みPDFを保存しました:\n{output_path}")
        else:
            self.log_message(f"タスク '{self.current_task}' が完了しました")

        self.current_task = None
        self.update_action_states()

    def on_task_error(self, error_msg: str):
        """タスクエラー時"""
        self.log_message(f"エラー: {error_msg}")
        QMessageBox.critical(self, "エラー", error_msg)
        self.app_state.status_message = "エラーが発生しました"
        self.current_task = None
        self.update_action_states()
