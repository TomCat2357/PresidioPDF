"""
PresidioPDF PyQt - 検出設定ダイアログ
"""

from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class DetectConfigDialog(QDialog):
    """検出エンティティ設定ダイアログ"""

    def __init__(
        self,
        entity_types: List[str],
        enabled_entities: List[str],
        config_path: Path,
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
        self._init_ui()
        self.set_enabled_entities(enabled_entities)

    def _init_ui(self):
        self.setWindowTitle("検出設定")
        self.setMinimumWidth(420)

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

    def _on_select_all_clicked(self):
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)
