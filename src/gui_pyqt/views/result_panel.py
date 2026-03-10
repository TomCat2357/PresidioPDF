"""
PresidioPDF PyQt - 検出結果パネル

Phase 4: 編集UI
- 検出結果テーブルの表示
- エンティティの削除機能
- エンティティタイプの編集機能
- テーブル選択時のシグナル発行
"""

import re
from typing import Optional, List, Dict, Any, Pattern
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMenu,
    QPushButton,
    QMessageBox,
    QDialog,
    QComboBox,
    QFormLayout,
    QDialogButtonBox,
    QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QItemSelectionModel
from PyQt6.QtGui import QAction, QShortcut, QKeySequence

from src.core.entity_types import ENTITY_TYPES, get_entity_type_name_ja


class ManualAddDialog(QDialog):
    """手動PII追記ダイアログ"""

    def __init__(self, preset_data: Optional[Dict] = None, parent=None):
        super().__init__(parent)
        self.preset_data = preset_data or {}
        self.init_ui()

    def init_ui(self):
        """UIの初期化"""
        self.setWindowTitle("エンティティ追加")
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QFormLayout()

        # 選択テキスト（読み取り専用）
        preset_text = str(self.preset_data.get("text", "") or "")
        self.text_label = QLabel(preset_text if preset_text != "" else "\"\"")
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addRow("選択テキスト:", self.text_label)

        # エンティティタイプの選択
        self.entity_type_combo = QComboBox()
        for etype in ENTITY_TYPES:
            self.entity_type_combo.addItem(get_entity_type_name_ja(etype), etype)
        layout.addRow("エンティティタイプ:", self.entity_type_combo)

        # ボタン
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self.setLayout(layout)

    def get_entity_data(self) -> Dict:
        """入力されたエンティティデータを取得"""
        text = str(self.preset_data.get("text", "") or "")
        entity_type = self.entity_type_combo.currentData()
        # 通常の手動追加（テキスト未選択）は従来どおり無効。
        # 選択モード由来の空文字 "" は有効。
        if not text and "text" not in self.preset_data:
            return {}

        # プリセットにstart/endがあればそれを優先。無ければ旧形式から補完。
        start_pos = self.preset_data.get("start")
        end_pos = self.preset_data.get("end")
        if not isinstance(start_pos, dict) or not isinstance(end_pos, dict):
            page_num = int(self.preset_data.get("page_num", 0) or 0)
            block_num = int(self.preset_data.get("block_num", 0) or 0)
            offset = int(self.preset_data.get("offset", 0) or 0)
            start_pos = {"page_num": page_num, "block_num": block_num, "offset": offset}
            end_pos = {
                "page_num": page_num,
                "block_num": block_num,
                "offset": offset + max(len(text) - 1, 0),
            }

        entity = {
            "word": text,
            "entity": entity_type,
            "start": start_pos,
            "end": end_pos,
            "origin": "manual",
            "manual": True,
        }

        # プリセットから rects_pdf を取得（存在する場合）
        rects_pdf = self.preset_data.get("rects_pdf")
        if rects_pdf:
            entity["rects_pdf"] = rects_pdf
        mask_rects_pdf = self.preset_data.get("mask_rects_pdf")
        if mask_rects_pdf:
            entity["mask_rects_pdf"] = mask_rects_pdf
        mask_circles_pdf = self.preset_data.get("mask_circles_pdf")
        if mask_circles_pdf:
            entity["mask_circles_pdf"] = mask_circles_pdf

        selection_mode = self.preset_data.get("selection_mode")
        if isinstance(selection_mode, str):
            entity["selection_mode"] = selection_mode

        return entity


class EntityEditDialog(QDialog):
    """エンティティ編集ダイアログ"""

    def __init__(self, entity: Dict, parent=None):
        super().__init__(parent)
        self.entity = entity
        self.init_ui()

    def init_ui(self):
        """UIの初期化"""
        self.setWindowTitle("エンティティの編集")
        self.setModal(True)

        layout = QFormLayout()

        # エンティティタイプの選択
        self.entity_type_combo = QComboBox()
        for etype in ENTITY_TYPES:
            self.entity_type_combo.addItem(get_entity_type_name_ja(etype), etype)

        # 現在の値を設定
        current_type = self.entity.get("entity", "")
        for i in range(self.entity_type_combo.count()):
            if self.entity_type_combo.itemData(i) == current_type:
                self.entity_type_combo.setCurrentIndex(i)
                break

        layout.addRow("エンティティタイプ:", self.entity_type_combo)

        # テキスト表示（読み取り専用）
        text_label = QLabel(self.entity.get("word", ""))
        layout.addRow("テキスト:", text_label)

        # ボタン
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self.setLayout(layout)

    def get_entity_type(self) -> str:
        """選択されたエンティティタイプを取得"""
        return self.entity_type_combo.currentData()


class ResultPanel(QWidget):
    """検出結果パネル（編集機能付き）"""

    # シグナル定義
    entity_selected = pyqtSignal(list)  # 選択されたエンティティ（複数）
    entity_deleted = pyqtSignal(int)  # 削除されたエンティティのインデックス
    entity_updated = pyqtSignal(int, dict)  # 更新されたエンティティ（インデックス、新しいデータ）
    entity_added = pyqtSignal(dict)  # 追加されたエンティティ
    register_selected_to_omit_requested = pyqtSignal(list)  # 選択項目をommitへ登録
    register_selected_to_add_requested = pyqtSignal(list)  # 選択項目をadd_entityへ登録
    select_current_page_requested = pyqtSignal()  # Ctrl+A: 表示ページの全選択要求

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entities: List[Dict] = []  # 現在表示中のエンティティリスト
        self._visible_entities: List[Dict] = []
        self._visible_entity_indices: List[int] = []
        self._sort_column: Optional[int] = None
        self._sort_ascending: bool = True
        self._filter_inputs: List[QLineEdit] = []
        self._filter_patterns: List[Optional[Pattern[str]]] = [None] * 5
        self.init_ui()

    def init_ui(self):
        """UIの初期化"""
        layout = QVBoxLayout()

        # ヘッダー
        header_layout = QHBoxLayout()
        header_label = QLabel("検出結果一覧:")
        header_layout.addWidget(header_label)

        self.count_label = QLabel("0件")
        self.count_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self.count_label)
        header_layout.addStretch()

        action_buttons_layout = QVBoxLayout()

        self.delete_button = QPushButton("🗑 選択を削除")
        self.delete_button.clicked.connect(self.delete_selected)
        self.delete_button.setEnabled(False)
        action_buttons_layout.addWidget(self.delete_button)

        self.omit_register_button = QPushButton("選択語を無視対象に登録")
        self.omit_register_button.clicked.connect(self.register_selected_to_omit)
        self.omit_register_button.setEnabled(False)
        action_buttons_layout.addWidget(self.omit_register_button)

        self.add_register_button = QPushButton("選択語を検出対象に登録")
        self.add_register_button.clicked.connect(self.register_selected_to_add)
        self.add_register_button.setEnabled(False)
        action_buttons_layout.addWidget(self.add_register_button)

        header_layout.addLayout(action_buttons_layout)

        layout.addLayout(header_layout)

        # フィルター入力ウィジェット作成（テーブルのrow 0に埋め込む）
        filter_columns = ["ページ", "種別", "テキスト", "位置", "検出元"]
        for col, column_name in enumerate(filter_columns):
            filter_input = QLineEdit(self)
            filter_input.setPlaceholderText(column_name)
            filter_input.textChanged.connect(self.on_filter_changed)
            self._filter_inputs.append(filter_input)

        # 検出結果テーブル
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "ページ", "種別", "テキスト", "位置", "検出元"
        ])
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self.show_context_menu)
        self.results_table.itemSelectionChanged.connect(self.on_selection_changed)
        self.results_table.itemDoubleClicked.connect(self.edit_selected)
        header = self.results_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self.on_header_clicked)
        header.setSortIndicatorShown(False)

        self.results_table.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #1a73e8;
                color: #ffffff;
            }
        """)
        # row 0 をフィルター行として固定
        self.results_table.setRowCount(1)
        for col, fi in enumerate(self._filter_inputs):
            self.results_table.setCellWidget(0, col, fi)

        # 列幅の初期設定
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # テキスト列: 残りスペース
        self.results_table.setColumnWidth(0, 45)   # ページ
        self.results_table.setColumnWidth(1, 90)   # 種別
        self.results_table.setColumnWidth(3, 130)  # 位置
        self.results_table.setColumnWidth(4, 45)   # 検出元

        # フィルター行（row 0）の垂直ヘッダーを空にする
        self.results_table.setVerticalHeaderLabels([""])

        layout.addWidget(self.results_table)

        self.setLayout(layout)

        # ショートカット: Delete / Ctrl+A（表示ページのみ）
        self.delete_shortcut = QShortcut(QKeySequence("Delete"), self.results_table)
        self.delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.delete_shortcut.activated.connect(self.delete_selected)

        self.select_current_page_shortcut = QShortcut(QKeySequence("Ctrl+A"), self.results_table)
        self.select_current_page_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.select_current_page_shortcut.activated.connect(
            self._on_select_current_page_shortcut
        )

        self.register_omit_shortcut = QShortcut(QKeySequence("Backspace"), self.results_table)
        self.register_omit_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.register_omit_shortcut.activated.connect(self.register_selected_to_omit)

        self.register_add_shortcut = QShortcut(QKeySequence("Insert"), self.results_table)
        self.register_add_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.register_add_shortcut.activated.connect(self.register_selected_to_add)

    def help_topic_for_widget(self, widget: Optional[QWidget]) -> Optional[str]:
        """対象ウィジェットに対応するヘルプトピックを返す"""
        if widget is None:
            return None

        targets = [
            self.results_table,
            self.delete_button,
            self.omit_register_button,
            self.add_register_button,
            *self._filter_inputs,
        ]
        for target in targets:
            if self._widget_matches_target(widget, target):
                return "result_table"
        return None

    @staticmethod
    def _widget_matches_target(widget: QWidget, target: QWidget) -> bool:
        """widget が target 自身またはその子孫かを判定する"""
        current = widget
        while current is not None:
            if current is target:
                return True
            current = current.parentWidget()
        return False

    def load_entities(self, result: Optional[dict]):
        """検出結果を読み込んでテーブルに表示"""
        if not result:
            self.entities = []
            self._visible_entities = []
            self._visible_entity_indices = []
            self.results_table.setRowCount(1)
            self.results_table.setVerticalHeaderLabels([""])
            self.count_label.setText("0件")
            self.delete_button.setEnabled(False)
            self.omit_register_button.setEnabled(False)
            self.add_register_button.setEnabled(False)
            return

        # detect配列を取得（新仕様形式）
        detect_list = result.get("detect", [])
        if not isinstance(detect_list, list):
            detect_list = []

        self.entities = self._dedupe_addition_vs_auto(list(detect_list))
        self.update_table()
        self.on_selection_changed()

    def on_filter_changed(self):
        """フィルター入力変更時に正規表現を更新"""
        for col, filter_input in enumerate(self._filter_inputs):
            expr = filter_input.text()
            if not expr:
                self._filter_patterns[col] = None
                filter_input.setStyleSheet("")
                continue
            try:
                self._filter_patterns[col] = re.compile(expr)
                filter_input.setStyleSheet("")
            except re.error:
                # 入力途中の不正な正規表現は赤枠で明示し、当該列の条件は無効化
                self._filter_patterns[col] = None
                filter_input.setStyleSheet("border: 1px solid #d93025;")

        self.update_table()
        self.on_selection_changed()

    def update_table(self):
        """テーブル表示を更新（1始まりで表示）"""
        self._apply_sort()
        self._rebuild_visible_entities()
        self.results_table.setRowCount(len(self._visible_entities) + 1)

        for i, entity in enumerate(self._visible_entities):
            # ページ番号（1始まりで表示）
            start_pos = entity.get("start", {})
            page_num = start_pos.get("page_num", 0) if isinstance(start_pos, dict) else 0
            self.results_table.setItem(i + 1, 0, QTableWidgetItem(str(page_num + 1)))

            # エンティティタイプ（日本語表示）
            entity_type = entity.get("entity", "")
            self.results_table.setItem(i + 1, 1, QTableWidgetItem(get_entity_type_name_ja(entity_type)))

            # テキスト
            text = entity.get("word", "")
            self.results_table.setItem(i + 1, 2, QTableWidgetItem(text))

            # 位置情報（1始まりで表示）
            end_pos = entity.get("end", {})
            if isinstance(start_pos, dict) and isinstance(end_pos, dict):
                block_num = start_pos.get('block_num', 0)
                offset = start_pos.get('offset', 0)
                position_str = f"p{page_num + 1}:b{block_num + 1}:{offset + 1}"
            else:
                position_str = ""
            self.results_table.setItem(i + 1, 3, QTableWidgetItem(position_str))

            # 検出元ラベル（手動／追加／自動）
            origin_label = self._get_origin_label(entity)
            self.results_table.setItem(i + 1, 4, QTableWidgetItem(origin_label))

        # 垂直ヘッダー: row 0（フィルター行）は空、以降は 1, 2, 3...
        v_labels = [""] + [str(i + 1) for i in range(len(self._visible_entities))]
        self.results_table.setVerticalHeaderLabels(v_labels)

        # カウント更新
        visible_count = len(self._visible_entities)
        total_count = len(self.entities)
        if visible_count == total_count:
            self.count_label.setText(f"{total_count}件")
        else:
            self.count_label.setText(f"{visible_count}件 / 全{total_count}件")

        # ソート状態のインジケータを更新
        header = self.results_table.horizontalHeader()
        if self._sort_column is None:
            header.setSortIndicatorShown(False)
        else:
            header.setSortIndicatorShown(True)
            order = (
                Qt.SortOrder.AscendingOrder
                if self._sort_ascending
                else Qt.SortOrder.DescendingOrder
            )
            header.setSortIndicator(self._sort_column, order)

    def on_header_clicked(self, column: int):
        """ヘッダークリックでソート順を切り替える"""
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True

        self.update_table()

    def _apply_sort(self):
        """現在のソート状態に従って entities を並べ替える"""
        if self._sort_column is None:
            return
        self.entities.sort(
            key=lambda entity: self._entity_sort_key(entity, self._sort_column),
            reverse=not self._sort_ascending,
        )

    def _rebuild_visible_entities(self):
        """正規表現フィルター（AND条件）で表示対象を再構築"""
        self._visible_entities = []
        self._visible_entity_indices = []
        for index, entity in enumerate(self.entities):
            if not self._matches_filters(entity):
                continue
            self._visible_entity_indices.append(index)
            self._visible_entities.append(entity)

    def _matches_filters(self, entity: Dict) -> bool:
        for col, pattern in enumerate(self._filter_patterns):
            if pattern is None:
                continue
            if pattern.search(self._entity_column_text(entity, col)) is None:
                return False
        return True

    @classmethod
    def _entity_column_text(cls, entity: Dict, column: int) -> str:
        start_pos = entity.get("start", {})
        end_pos = entity.get("end", {})
        if not isinstance(start_pos, dict):
            start_pos = {}
        if not isinstance(end_pos, dict):
            end_pos = {}

        page_num = cls._safe_int(start_pos.get("page_num", 0))
        block_num = cls._safe_int(start_pos.get("block_num", 0))
        offset = cls._safe_int(start_pos.get("offset", 0))

        if column == 0:
            return str(page_num + 1)
        if column == 1:
            return get_entity_type_name_ja(str(entity.get("entity", "")))
        if column == 2:
            return str(entity.get("word", ""))
        if column == 3:
            if isinstance(start_pos, dict) and isinstance(end_pos, dict):
                return f"p{page_num + 1}:b{block_num + 1}:{offset + 1}"
            return ""
        if column == 4:
            return cls._get_origin_label(entity)
        return ""

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """値を整数へ安全に変換する"""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _get_origin_label(entity: Dict) -> str:
        """エンティティの検出元ラベルを返す（手動／追加／自動）"""
        if not isinstance(entity, dict):
            return "自動"
        if entity.get("manual") is True:
            return "手動"
        origin = str(entity.get("origin", "")).strip().lower()
        if origin == "manual":
            return "手動"
        if origin == "custom":
            return "追加"
        return "自動"

    @classmethod
    def _dedupe_addition_vs_auto(cls, entities: List[Dict]) -> List[Dict]:
        """追加と自動が同じエンティティ・同じ位置の場合は自動のみ残す"""
        from collections import defaultdict
        span_map: Dict[Any, List[int]] = defaultdict(list)
        no_key_indices: List[int] = []
        for i, entity in enumerate(entities):
            if not isinstance(entity, dict):
                no_key_indices.append(i)
                continue
            start_pos = entity.get("start", {})
            end_pos = entity.get("end", {})
            if not isinstance(start_pos, dict) or not isinstance(end_pos, dict):
                no_key_indices.append(i)
                continue
            span_key = (
                str(entity.get("entity", "")),
                start_pos.get("page_num"),
                start_pos.get("block_num"),
                start_pos.get("offset"),
                end_pos.get("page_num"),
                end_pos.get("block_num"),
                end_pos.get("offset"),
            )
            span_map[span_key].append(i)

        remove_indices: set = set()
        for idxs in span_map.values():
            if len(idxs) <= 1:
                continue
            has_auto = any(cls._get_origin_label(entities[i]) == "自動" for i in idxs)
            if has_auto:
                for i in idxs:
                    if cls._get_origin_label(entities[i]) == "追加":
                        remove_indices.add(i)

        return [e for i, e in enumerate(entities) if i not in remove_indices]

    @classmethod
    def _entity_sort_key(cls, entity: Dict, column: int):
        """列に応じたソートキーを返す"""
        if not isinstance(entity, dict):
            return ()

        start_pos = entity.get("start", {})
        end_pos = entity.get("end", {})
        if not isinstance(start_pos, dict):
            start_pos = {}
        if not isinstance(end_pos, dict):
            end_pos = {}

        page_num = cls._safe_int(start_pos.get("page_num", 0))
        block_num = cls._safe_int(start_pos.get("block_num", 0))
        offset = cls._safe_int(start_pos.get("offset", 0))
        end_page_num = cls._safe_int(end_pos.get("page_num", page_num))
        end_block_num = cls._safe_int(end_pos.get("block_num", block_num))
        end_offset = cls._safe_int(end_pos.get("offset", offset))

        if column == 0:
            return (page_num, block_num, offset)
        if column == 1:
            return str(entity.get("entity", "")).lower()
        if column == 2:
            return str(entity.get("word", "")).lower()
        if column == 3:
            return (page_num, block_num, offset, end_page_num, end_block_num, end_offset)
        if column == 4:
            label = cls._get_origin_label(entity)
            order = {"手動": 0, "追加": 1, "自動": 2}
            return order.get(label, 3)
        return str(entity)

    def _on_select_current_page_shortcut(self):
        """Ctrl+Aが押されたときに表示ページ全選択を要求"""
        self.select_current_page_requested.emit()

    def show_context_menu(self, pos):
        """コンテキストメニューを表示"""
        if self.results_table.rowCount() == 0:
            return

        menu = QMenu(self)

        edit_action = QAction("編集", self)
        edit_action.triggered.connect(self.edit_selected)
        menu.addAction(edit_action)

        delete_action = QAction("削除", self)
        delete_action.triggered.connect(self.delete_selected)
        menu.addAction(delete_action)

        menu.exec(self.results_table.viewport().mapToGlobal(pos))

    def on_selection_changed(self):
        """選択状態が変更された"""
        selected_rows = self.get_selected_rows()
        has_selection = len(selected_rows) > 0
        self.delete_button.setEnabled(has_selection)
        self.omit_register_button.setEnabled(has_selection)
        self.add_register_button.setEnabled(has_selection)

        # 選択されたエンティティのリストを取得
        selected_entities = [
            self._visible_entities[row]
            for row in selected_rows
            if row < len(self._visible_entities)
        ]
        self.entity_selected.emit(selected_entities)

    def clear_entity_selection(self):
        """テーブル選択を明示的に解除し、空選択を通知する"""
        selection_model = self.results_table.selectionModel()
        if selection_model is not None:
            selection_model.clearSelection()
            selection_model.clearCurrentIndex()
        self.results_table.clearSelection()
        self.on_selection_changed()

    def focus_results_table(self):
        """結果テーブルにフォーカスを移す"""
        self.results_table.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def register_selected_to_omit(self):
        """選択語を無視対象（ommit_entity）へ登録する"""
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "登録する項目を選択してください")
            return
        count = len(selected_rows)
        reply = QMessageBox.question(
            self,
            "確認",
            f"{count}件を無視対象に登録しますか?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        selected_entities = [
            self._visible_entities[row]
            for row in selected_rows
            if row < len(self._visible_entities)
        ]
        self.register_selected_to_omit_requested.emit(selected_entities)

    def register_selected_to_add(self):
        """選択語を検出対象（add_entity）へ登録する"""
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "登録する項目を選択してください")
            return
        count = len(selected_rows)
        reply = QMessageBox.question(
            self,
            "確認",
            f"{count}件を検出対象に登録しますか?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        selected_entities = [
            self._visible_entities[row]
            for row in selected_rows
            if row < len(self._visible_entities)
        ]
        self.register_selected_to_add_requested.emit(selected_entities)

    def get_selected_rows(self) -> List[int]:
        """選択されている行のインデックスリストを取得"""
        selected_items = self.results_table.selectedItems()
        if not selected_items:
            return []

        # 行番号を重複なく取得（row 0 はフィルター行のため除外し、-1 してデータ行インデックスに変換）
        selected_rows = sorted(set(
            item.row() - 1 for item in selected_items if item.row() > 0
        ))
        return selected_rows

    def edit_selected(self):
        """選択されたエンティティを編集"""
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "編集する項目を選択してください")
            return

        # 最初の選択項目のみ編集
        visible_row = selected_rows[0]
        if visible_row >= len(self._visible_entities):
            return

        row = self._visible_entity_indices[visible_row]
        entity = self.entities[row]

        # 編集ダイアログを表示
        dialog = EntityEditDialog(entity, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # エンティティタイプを更新
            new_type = dialog.get_entity_type()
            entity["entity"] = new_type

            # テーブルを更新
            self.update_table()

            # シグナル発行
            self.entity_updated.emit(row, entity)

    def delete_selected(self):
        """選択されたエンティティを削除"""
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "削除する項目を選択してください")
            return

        # 確認ダイアログ
        count = len(selected_rows)
        reply = QMessageBox.question(
            self,
            "確認",
            f"{count}件のエンティティを削除しますか?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # 後ろから削除（インデックスがずれないように）
        delete_rows = []
        for visible_row in selected_rows:
            if visible_row < len(self._visible_entity_indices):
                delete_rows.append(self._visible_entity_indices[visible_row])

        for row in sorted(set(delete_rows), reverse=True):
            if row < len(self.entities):
                del self.entities[row]
                self.entity_deleted.emit(row)

        # テーブル更新後に選択を必ず空へ戻す（他行の自動選択を防止）
        self.results_table.blockSignals(True)
        try:
            self.update_table()
            selection_model = self.results_table.selectionModel()
            if selection_model is not None:
                selection_model.clearSelection()
                selection_model.clearCurrentIndex()
            self.results_table.clearSelection()
        finally:
            self.results_table.blockSignals(False)
        self.on_selection_changed()

    def select_row(self, row: int):
        """指定行を選択してスクロール表示する"""
        if row in self._visible_entity_indices:
            visible_row = self._visible_entity_indices.index(row)
            self.results_table.selectRow(visible_row + 1)
            self.results_table.scrollToItem(
                self.results_table.item(visible_row + 1, 0),
                QTableWidget.ScrollHint.PositionAtCenter,
            )

    def select_rows(self, rows: List[int]):
        """指定行を複数選択する"""
        self.results_table.clearSelection()
        selection_model = self.results_table.selectionModel()
        if selection_model is None:
            return

        visible_rows = []
        for row in rows:
            if row not in self._visible_entity_indices:
                continue
            visible_row = self._visible_entity_indices.index(row)
            visible_rows.append(visible_row)
            index = self.results_table.model().index(visible_row + 1, 0)
            selection_model.select(
                index,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )

        if visible_rows:
            first_row = min(visible_rows)
            self.results_table.scrollToItem(
                self.results_table.item(first_row + 1, 0),
                QTableWidget.ScrollHint.PositionAtCenter,
            )

    def get_entities(self) -> List[Dict]:
        """現在のエンティティリストを取得"""
        return self.entities

    def add_manual_entity(self, preset_data: Optional[Dict] = None):
        """手動PII追加ダイアログを表示"""
        dialog = ManualAddDialog(preset_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            entity = dialog.get_entity_data()
            if not entity:
                return
            # エンティティをリストに追加
            self.entities.append(entity)
            # テーブルを更新
            self.update_table()
            # シグナル発行
            self.entity_added.emit(entity)
