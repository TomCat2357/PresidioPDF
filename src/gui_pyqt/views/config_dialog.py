"""
PresidioPDF PyQt - 検出設定ダイアログ
"""

from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)
from PyQt6.QtGui import QStandardItem

from src.core.entity_types import get_entity_type_name_ja


class DetectConfigDialog(QDialog):
    """検出エンティティ設定ダイアログ"""

    def __init__(
        self,
        entity_types: List[str],
        enabled_entities: List[str],
        config_path: Path,
        duplicate_entity_overlap_mode: str = "any",
        duplicate_overlap_mode: str = "overlap",
        spacy_model: str = "ja_core_news_trf",
        installed_models: Optional[List[str]] = None,
        all_models: Optional[List[str]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.entity_types = list(entity_types or [])
        self.config_path = Path(config_path)
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.select_all_button: Optional[QPushButton] = None
        self.open_json_button: Optional[QPushButton] = None
        self.import_button: Optional[QPushButton] = None
        self.export_button: Optional[QPushButton] = None
        self.entity_overlap_same_radio: Optional[QRadioButton] = None
        self.entity_overlap_any_radio: Optional[QRadioButton] = None
        self.overlap_contain_radio: Optional[QRadioButton] = None
        self.overlap_overlap_radio: Optional[QRadioButton] = None
        self.model_combo: Optional[QComboBox] = None
        self._installed_models: List[str] = list(installed_models or [])
        self._all_models: List[str] = list(all_models or [])
        self._init_ui()
        self.set_enabled_entities(enabled_entities)
        self.set_duplicate_settings(
            duplicate_entity_overlap_mode,
            duplicate_overlap_mode,
        )
        self.set_spacy_model(spacy_model)

    def _init_ui(self):
        self.setWindowTitle("設定")
        self.setMinimumWidth(520)

        layout = QVBoxLayout()

        info = QLabel(
            "チェックしたエンティティのみ検出します。\n"
            f"設定ファイル: {self.config_path}"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        for entity in self.entity_types:
            checkbox = QCheckBox(get_entity_type_name_ja(entity))
            self.checkboxes[entity] = checkbox
            layout.addWidget(checkbox)

        select_row = QHBoxLayout()
        self.select_all_button = QPushButton("全選択")
        self.select_all_button.clicked.connect(self._on_select_all_clicked)
        select_row.addWidget(self.select_all_button)
        select_row.addStretch()
        layout.addLayout(select_row)

        # spaCyモデル選択
        model_group = QGroupBox("spaCyモデル")
        model_layout = QHBoxLayout()
        model_label = QLabel("使用モデル:")
        self.model_combo = QComboBox()
        for model_name in self._all_models:
            if model_name in self._installed_models:
                self.model_combo.addItem(model_name, model_name)
            else:
                label = f"{model_name} (未インストール)"
                self.model_combo.addItem(label, model_name)
                idx = self.model_combo.count() - 1
                item = self.model_combo.model().item(idx)
                if isinstance(item, QStandardItem):
                    item.setEnabled(False)
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        duplicate_group = QGroupBox("重複削除設定")
        duplicate_layout = QVBoxLayout()

        entity_mode_label = QLabel("エンティティ重複判定")
        self.entity_overlap_any_radio = QRadioButton("異なるエンティティでも同一扱い")
        self.entity_overlap_same_radio = QRadioButton("同じエンティティのみ")
        self._entity_overlap_group = QButtonGroup(self)
        self._entity_overlap_group.addButton(self.entity_overlap_any_radio)
        self._entity_overlap_group.addButton(self.entity_overlap_same_radio)
        duplicate_layout.addWidget(entity_mode_label)
        duplicate_layout.addWidget(self.entity_overlap_any_radio)
        duplicate_layout.addWidget(self.entity_overlap_same_radio)

        overlap_mode_label = QLabel("重複判定")
        self.overlap_contain_radio = QRadioButton("包含関係のみ")
        self.overlap_overlap_radio = QRadioButton("一部重なりも含む")
        self._overlap_group = QButtonGroup(self)
        self._overlap_group.addButton(self.overlap_contain_radio)
        self._overlap_group.addButton(self.overlap_overlap_radio)
        duplicate_layout.addWidget(overlap_mode_label)
        duplicate_layout.addWidget(self.overlap_contain_radio)
        duplicate_layout.addWidget(self.overlap_overlap_radio)

        duplicate_group.setLayout(duplicate_layout)
        layout.addWidget(duplicate_group)

        action_row = QHBoxLayout()
        self.open_json_button = QPushButton(".config.jsonを開く")
        self.import_button = QPushButton("インポート")
        self.export_button = QPushButton("エクスポート")
        action_row.addWidget(self.open_json_button)
        action_row.addWidget(self.import_button)
        action_row.addWidget(self.export_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def set_enabled_entities(self, enabled_entities: List[str]):
        enabled = {str(name).strip().upper() for name in (enabled_entities or [])}
        for entity, checkbox in self.checkboxes.items():
            checkbox.setChecked(entity in enabled)

    def get_enabled_entities(self) -> List[str]:
        result = []
        for entity in self.entity_types:
            checkbox = self.checkboxes.get(entity)
            if checkbox and checkbox.isChecked():
                result.append(entity)
        return result

    def set_duplicate_settings(self, entity_overlap_mode: str, overlap_mode: str):
        entity_mode = str(entity_overlap_mode or "any").strip().lower()
        if self.entity_overlap_same_radio and self.entity_overlap_any_radio:
            if entity_mode == "same":
                self.entity_overlap_same_radio.setChecked(True)
            else:
                self.entity_overlap_any_radio.setChecked(True)

        overlap = str(overlap_mode or "overlap").strip().lower()
        if self.overlap_contain_radio and self.overlap_overlap_radio:
            if overlap == "contain":
                self.overlap_contain_radio.setChecked(True)
            else:
                self.overlap_overlap_radio.setChecked(True)

    def get_duplicate_settings(self) -> Dict[str, str]:
        entity_overlap_mode = "any"
        if self.entity_overlap_same_radio and self.entity_overlap_same_radio.isChecked():
            entity_overlap_mode = "same"

        overlap_mode = "overlap"
        if self.overlap_contain_radio and self.overlap_contain_radio.isChecked():
            overlap_mode = "contain"

        return {
            "entity_overlap_mode": entity_overlap_mode,
            "overlap": overlap_mode,
        }

    def get_spacy_model(self) -> str:
        if self.model_combo:
            return self.model_combo.currentData() or ""
        return ""

    def set_spacy_model(self, model_name: str):
        if not self.model_combo:
            return
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == model_name:
                self.model_combo.setCurrentIndex(i)
                return

    def _on_select_all_clicked(self):
        checkboxes = list(self.checkboxes.values())
        if not checkboxes:
            return

        should_select_all = not all(checkbox.isChecked() for checkbox in checkboxes)
        for checkbox in checkboxes:
            checkbox.setChecked(should_select_all)
