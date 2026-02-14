"""
PresidioPDF PyQt - 検出結果パネル

Phase 4: 編集UI
- 検出結果テーブルの表示
- エンティティの削除機能
- エンティティタイプの編集機能
- テーブル選択時のシグナル発行
"""

from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QMenu,
    QPushButton,
    QMessageBox,
    QDialog,
    QComboBox,
    QFormLayout,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction


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
        self.text_label = QLabel(preset_text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addRow("選択テキスト:", self.text_label)

        # エンティティタイプの選択
        self.entity_type_combo = QComboBox()
        entity_types = [
            "PERSON",
            "LOCATION",
            "DATE_TIME",
            "PHONE_NUMBER",
            "INDIVIDUAL_NUMBER",
            "YEAR",
            "PROPER_NOUN",
            "OTHER",
        ]
        self.entity_type_combo.addItems(entity_types)
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
        text = str(self.preset_data.get("text", "") or "").strip()
        entity_type = self.entity_type_combo.currentText()
        if not text:
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
        entity_types = [
            "PERSON",
            "LOCATION",
            "DATE_TIME",
            "PHONE_NUMBER",
            "INDIVIDUAL_NUMBER",
            "YEAR",
            "PROPER_NOUN",
            "OTHER",
        ]
        self.entity_type_combo.addItems(entity_types)

        # 現在の値を設定
        current_type = self.entity.get("entity", "")
        if current_type in entity_types:
            self.entity_type_combo.setCurrentText(current_type)

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
        return self.entity_type_combo.currentText()


class ResultPanel(QWidget):
    """検出結果パネル（編集機能付き）"""

    # シグナル定義
    entity_selected = pyqtSignal(list)  # 選択されたエンティティ（複数）
    entity_deleted = pyqtSignal(int)  # 削除されたエンティティのインデックス
    entity_updated = pyqtSignal(int, dict)  # 更新されたエンティティ（インデックス、新しいデータ）
    entity_added = pyqtSignal(dict)  # 追加されたエンティティ

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entities: List[Dict] = []  # 現在表示中のエンティティリスト
        self._sort_column: Optional[int] = None
        self._sort_ascending: bool = True
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

        self.delete_button = QPushButton("🗑 選択を削除")
        self.delete_button.clicked.connect(self.delete_selected)
        self.delete_button.setEnabled(False)
        header_layout.addWidget(self.delete_button)

        layout.addLayout(header_layout)

        # 検出結果テーブル
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "ページ", "Entity Type", "テキスト", "信頼度", "位置", "手動"
        ])
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self.show_context_menu)
        self.results_table.itemSelectionChanged.connect(self.on_selection_changed)
        self.results_table.itemDoubleClicked.connect(self.edit_selected)
        header = self.results_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self.on_header_clicked)
        header.setSortIndicatorShown(False)

        layout.addWidget(self.results_table)

        self.setLayout(layout)

    def load_entities(self, result: Optional[dict]):
        """検出結果を読み込んでテーブルに表示"""
        if not result:
            self.entities = []
            self.results_table.setRowCount(0)
            self.count_label.setText("0件")
            return

        # detect配列を取得（新仕様形式）
        detect_list = result.get("detect", [])
        if not isinstance(detect_list, list):
            detect_list = []

        self.entities = list(detect_list)
        self.update_table()

    def update_table(self):
        """テーブル表示を更新（1始まりで表示）"""
        self._apply_sort()
        self.results_table.setRowCount(len(self.entities))

        for i, entity in enumerate(self.entities):
            # ページ番号（1始まりで表示）
            start_pos = entity.get("start", {})
            page_num = start_pos.get("page_num", 0) if isinstance(start_pos, dict) else 0
            self.results_table.setItem(i, 0, QTableWidgetItem(str(page_num + 1)))

            # エンティティタイプ
            entity_type = entity.get("entity", "")
            self.results_table.setItem(i, 1, QTableWidgetItem(entity_type))

            # テキスト
            text = entity.get("word", "")
            self.results_table.setItem(i, 2, QTableWidgetItem(text))

            # 信頼度（origin）
            origin = entity.get("origin", "")
            self.results_table.setItem(i, 3, QTableWidgetItem(origin))

            # 位置情報（1始まりで表示）
            end_pos = entity.get("end", {})
            if isinstance(start_pos, dict) and isinstance(end_pos, dict):
                block_num = start_pos.get('block_num', 0)
                offset = start_pos.get('offset', 0)
                position_str = f"p{page_num + 1}:b{block_num + 1}:{offset + 1}"
            else:
                position_str = ""
            self.results_table.setItem(i, 4, QTableWidgetItem(position_str))

            # 手動追加フラグ
            is_manual = self._is_manual_entity(entity)
            manual_str = "✓" if is_manual else ""
            self.results_table.setItem(i, 5, QTableWidgetItem(manual_str))

        # テーブルのリサイズ
        self.results_table.resizeColumnsToContents()

        # カウント更新
        self.count_label.setText(f"{len(self.entities)}件")

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

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """値を整数へ安全に変換する"""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _is_manual_entity(entity: Dict) -> bool:
        """手動追加項目かどうかを判定"""
        if not isinstance(entity, dict):
            return False
        if entity.get("manual") is True:
            return True
        return str(entity.get("origin", "")).lower() == "manual"

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
            return str(entity.get("origin", "")).lower()
        if column == 4:
            return (page_num, block_num, offset, end_page_num, end_block_num, end_offset)
        if column == 5:
            return 1 if cls._is_manual_entity(entity) else 0
        return str(entity)

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
        self.delete_button.setEnabled(len(selected_rows) > 0)

        # 選択されたエンティティのリストを取得
        selected_entities = [self.entities[row] for row in selected_rows if row < len(self.entities)]
        self.entity_selected.emit(selected_entities)

    def get_selected_rows(self) -> List[int]:
        """選択されている行のインデックスリストを取得"""
        selected_items = self.results_table.selectedItems()
        if not selected_items:
            return []

        # 行番号を重複なく取得
        selected_rows = sorted(set(item.row() for item in selected_items))
        return selected_rows

    def edit_selected(self):
        """選択されたエンティティを編集"""
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "編集する項目を選択してください")
            return

        # 最初の選択項目のみ編集
        row = selected_rows[0]
        if row >= len(self.entities):
            return

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
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # 後ろから削除（インデックスがずれないように）
        for row in sorted(selected_rows, reverse=True):
            if row < len(self.entities):
                del self.entities[row]
                self.entity_deleted.emit(row)

        # テーブルを更新
        self.update_table()
        self.on_selection_changed()

    def select_row(self, row: int):
        """指定行を選択してスクロール表示する"""
        if 0 <= row < self.results_table.rowCount():
            self.results_table.selectRow(row)
            self.results_table.scrollToItem(
                self.results_table.item(row, 0),
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
