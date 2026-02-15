"""
PresidioPDF PyQt - 検出設定ダイアログ
"""

from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)


class DetectConfigDialog(QDialog):
    """検出エンティティ設定ダイアログ"""

    def __init__(
        self,
        entity_types: List[str],
        enabled_entities: List[str],
        config_path: Path,
        duplicate_entity_overlap_mode: str = "any",
        duplicate_overlap_mode: str = "overlap",
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
        self._init_ui()
        self.set_enabled_entities(enabled_entities)
        self.set_duplicate_settings(
            duplicate_entity_overlap_mode,
            duplicate_overlap_mode,
        )

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
            checkbox = QCheckBox(entity)
            self.checkboxes[entity] = checkbox
            layout.addWidget(checkbox)

        select_row = QHBoxLayout()
        self.select_all_button = QPushButton("全選択")
        self.select_all_button.clicked.connect(self._on_select_all_clicked)
        select_row.addWidget(self.select_all_button)
        select_row.addStretch()
        layout.addLayout(select_row)

        duplicate_group = QGroupBox("重複削除設定")
        duplicate_layout = QVBoxLayout()

        entity_mode_label = QLabel("エンティティ重複判定")
        self.entity_overlap_any_radio = QRadioButton("異なるエンティティでも同一扱い")
        self.entity_overlap_same_radio = QRadioButton("同じエンティティのみ")
        duplicate_layout.addWidget(entity_mode_label)
        duplicate_layout.addWidget(self.entity_overlap_any_radio)
        duplicate_layout.addWidget(self.entity_overlap_same_radio)

        overlap_mode_label = QLabel("重複判定")
        self.overlap_contain_radio = QRadioButton("包含関係のみ")
        self.overlap_overlap_radio = QRadioButton("一部重なりも含む")
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

    def _on_select_all_clicked(self):
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)
