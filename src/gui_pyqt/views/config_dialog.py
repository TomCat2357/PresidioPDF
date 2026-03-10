"""
PresidioPDF PyQt - 検出設定ダイアログ
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from PyQt6.QtCore import QFileSystemWatcher, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from src.core.entity_types import get_entity_type_name_ja
from src.gui_pyqt.services.detect_config_service import DetectConfigService


class DetectConfigDialog(QDialog):
    """検出エンティティ設定ダイアログ"""

    DISPLAY_CONFIG_NAME = "config.json"

    def __init__(
        self,
        entity_types: List[str],
        enabled_entities: List[str],
        config_path: Path,
        duplicate_entity_overlap_mode: str = "any",
        duplicate_overlap_mode: str = "overlap",
        spacy_model: str = "ja_core_news_sm",
        installed_models: Optional[List[str]] = None,
        all_models: Optional[List[str]] = None,
        chunk_delimiter: str = "。",
        chunk_max_chars: int = 15000,
        ignore_newlines: bool = True,
        ignore_whitespace: bool = False,
        ocr_font_color: Optional[List[int]] = None,
        ocr_opacity: float = 0.0,
        ocr_before_detect: bool = False,
        ocr_auto_color: bool = False,
        ocr_offset_x: float = 0.0,
        ocr_offset_y: float = 0.0,
        ocr_available: bool = False,
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
        self.chunk_delimiter_edit: Optional[QLineEdit] = None
        self.chunk_max_chars_spin: Optional[QSpinBox] = None
        self.ignore_newlines_checkbox: Optional[QCheckBox] = None
        self.ignore_whitespace_checkbox: Optional[QCheckBox] = None
        self.ocr_status_label: Optional[QLabel] = None
        self.ocr_color_button: Optional[QPushButton] = None
        self.ocr_opacity_slider: Optional[QSlider] = None
        self.ocr_opacity_spin: Optional[QSpinBox] = None
        self.ocr_before_detect_checkbox: Optional[QCheckBox] = None
        self.ocr_auto_color_checkbox: Optional[QCheckBox] = None
        self.ocr_offset_x_spin: Optional[QDoubleSpinBox] = None
        self.ocr_offset_y_spin: Optional[QDoubleSpinBox] = None
        self._ocr_color: List[int] = [0, 0, 0]
        self._ocr_available = bool(ocr_available)
        self._installed_models: List[str] = list(installed_models or [])
        self._all_models: List[str] = list(all_models or [])
        self._file_watcher: Optional[QFileSystemWatcher] = None
        self._suspend_auto_save = False
        self._init_ui()
        self.set_enabled_entities(enabled_entities)
        self.set_duplicate_settings(
            duplicate_entity_overlap_mode,
            duplicate_overlap_mode,
        )
        self.set_spacy_model(spacy_model)
        self.set_chunk_settings(chunk_delimiter, chunk_max_chars)
        self.set_text_preprocess_settings(ignore_newlines, ignore_whitespace)
        self.set_ocr_settings(
            font_color=ocr_font_color
            or DetectConfigService.DEFAULT_OCR_SETTINGS["font_color"],
            opacity=ocr_opacity,
            ocr_before_detect=ocr_before_detect,
            auto_color=ocr_auto_color,
            offset_x=ocr_offset_x,
            offset_y=ocr_offset_y,
        )
        self._start_watching()

    def _init_ui(self):
        self.setWindowTitle("設定")
        self.setMinimumWidth(520)

        layout = QVBoxLayout()

        info = QLabel("チェックした対象のみ検出します。")
        info.setWordWrap(True)
        layout.addWidget(info)

        entity_group = QGroupBox("検出対象")
        entity_layout = QGridLayout()
        for entity in self.entity_types:
            checkbox = QCheckBox(get_entity_type_name_ja(entity))
            self.checkboxes[entity] = checkbox
            index = len(self.checkboxes) - 1
            row = index // 2
            column = index % 2
            entity_layout.addWidget(checkbox, row, column)
        entity_layout.setColumnStretch(0, 1)
        entity_layout.setColumnStretch(1, 1)
        entity_group.setLayout(entity_layout)
        layout.addWidget(entity_group)

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
        if self._installed_models:
            for model_name in self._installed_models:
                self.model_combo.addItem(model_name, model_name)
        else:
            self.model_combo.addItem("(インストール済みモデルなし)", "")
            self.model_combo.setEnabled(False)
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        duplicate_group = QGroupBox("重複削除設定")
        duplicate_layout = QVBoxLayout()

        entity_mode_label = QLabel("対象重複判定")
        self.entity_overlap_any_radio = QRadioButton("異なる対象でも同一扱い")
        self.entity_overlap_same_radio = QRadioButton("同じ対象のみ")
        self._entity_overlap_group = QButtonGroup(self)
        self._entity_overlap_group.addButton(self.entity_overlap_any_radio)
        self._entity_overlap_group.addButton(self.entity_overlap_same_radio)
        duplicate_layout.addWidget(entity_mode_label)
        entity_mode_row = QHBoxLayout()
        entity_mode_row.addWidget(self.entity_overlap_any_radio)
        entity_mode_row.addWidget(self.entity_overlap_same_radio)
        entity_mode_row.addStretch()
        duplicate_layout.addLayout(entity_mode_row)

        overlap_mode_label = QLabel("重複判定")
        self.overlap_contain_radio = QRadioButton("包含関係のみ")
        self.overlap_overlap_radio = QRadioButton("一部重なりも含む")
        self._overlap_group = QButtonGroup(self)
        self._overlap_group.addButton(self.overlap_contain_radio)
        self._overlap_group.addButton(self.overlap_overlap_radio)
        duplicate_layout.addWidget(overlap_mode_label)
        overlap_mode_row = QHBoxLayout()
        overlap_mode_row.addWidget(self.overlap_contain_radio)
        overlap_mode_row.addWidget(self.overlap_overlap_radio)
        overlap_mode_row.addStretch()
        duplicate_layout.addLayout(overlap_mode_row)

        duplicate_group.setLayout(duplicate_layout)
        layout.addWidget(duplicate_group)

        preprocess_group = QGroupBox("テキスト前処理設定")
        preprocess_layout = QVBoxLayout()
        self.ignore_newlines_checkbox = QCheckBox(
            "改行無視（OFF時はブロック/ページ境界に改行を挿入）"
        )
        self.ignore_whitespace_checkbox = QCheckBox("空白無視（空白文字を除去）")
        preprocess_layout.addWidget(self.ignore_newlines_checkbox)
        preprocess_layout.addWidget(self.ignore_whitespace_checkbox)
        preprocess_group.setLayout(preprocess_layout)
        layout.addWidget(preprocess_group)

        ocr_group = QGroupBox("OCR設定 (NDLOCR-Lite)")
        ocr_layout = QVBoxLayout()
        self.ocr_status_label = QLabel()
        self.ocr_status_label.setWordWrap(True)
        if not self._ocr_available:
            self.ocr_status_label.setText(
                "NDLOCR-Liteが未インストールのためOCRは無効です。"
            )
            ocr_layout.addWidget(self.ocr_status_label)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("埋め込みテキスト色:"))
        self.ocr_color_button = QPushButton("色を選択...")
        self.ocr_color_button.clicked.connect(self._choose_ocr_color)
        color_row.addWidget(self.ocr_color_button)
        color_row.addStretch()
        ocr_layout.addLayout(color_row)

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("透明度:"))
        self.ocr_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.ocr_opacity_slider.setRange(0, 100)
        self.ocr_opacity_spin = QSpinBox()
        self.ocr_opacity_spin.setRange(0, 100)
        self.ocr_opacity_spin.setSuffix("%")
        self.ocr_opacity_slider.valueChanged.connect(self.ocr_opacity_spin.setValue)
        self.ocr_opacity_spin.valueChanged.connect(self.ocr_opacity_slider.setValue)
        opacity_row.addWidget(self.ocr_opacity_slider, 1)
        opacity_row.addWidget(self.ocr_opacity_spin)
        ocr_layout.addLayout(opacity_row)

        offset_row = QHBoxLayout()
        offset_row.addWidget(QLabel("Xオフセット (pt):"))
        self.ocr_offset_x_spin = QDoubleSpinBox()
        self.ocr_offset_x_spin.setRange(-1000.0, 1000.0)
        self.ocr_offset_x_spin.setDecimals(2)
        self.ocr_offset_x_spin.setSingleStep(0.1)
        offset_row.addWidget(self.ocr_offset_x_spin)
        offset_row.addWidget(QLabel("Yオフセット (pt):"))
        self.ocr_offset_y_spin = QDoubleSpinBox()
        self.ocr_offset_y_spin.setRange(-1000.0, 1000.0)
        self.ocr_offset_y_spin.setDecimals(2)
        self.ocr_offset_y_spin.setSingleStep(0.1)
        offset_row.addWidget(self.ocr_offset_y_spin)
        offset_row.addStretch()
        ocr_layout.addLayout(offset_row)

        ocr_checkbox_row = QHBoxLayout()
        self.ocr_before_detect_checkbox = QCheckBox("個人情報検出時にOCRを先行実行する")
        self.ocr_before_detect_checkbox.setEnabled(self._ocr_available)
        ocr_checkbox_row.addWidget(self.ocr_before_detect_checkbox)
        self.ocr_auto_color_checkbox = QCheckBox("テキスト色を画像から自動検出")
        self.ocr_auto_color_checkbox.setEnabled(self._ocr_available)
        ocr_checkbox_row.addWidget(self.ocr_auto_color_checkbox)
        ocr_checkbox_row.addStretch()
        ocr_layout.addLayout(ocr_checkbox_row)

        if not self._ocr_available:
            if self.ocr_color_button:
                self.ocr_color_button.setEnabled(False)
            if self.ocr_opacity_slider:
                self.ocr_opacity_slider.setEnabled(False)
            if self.ocr_opacity_spin:
                self.ocr_opacity_spin.setEnabled(False)
            if self.ocr_offset_x_spin:
                self.ocr_offset_x_spin.setEnabled(False)
            if self.ocr_offset_y_spin:
                self.ocr_offset_y_spin.setEnabled(False)

        ocr_group.setLayout(ocr_layout)
        layout.addWidget(ocr_group)

        action_row = QHBoxLayout()
        self.open_json_button = QPushButton(self.DISPLAY_CONFIG_NAME)
        self.import_button = QPushButton("インポート")
        self.export_button = QPushButton("エクスポート")
        action_row.addWidget(self.open_json_button)
        action_row.addWidget(self.import_button)
        action_row.addWidget(self.export_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self._connect_auto_save_signals()

    def _connect_auto_save_signals(self):
        for checkbox in self.checkboxes.values():
            checkbox.toggled.connect(self._on_ui_value_changed)
        if self.entity_overlap_same_radio:
            self.entity_overlap_same_radio.toggled.connect(self._on_ui_value_changed)
        if self.entity_overlap_any_radio:
            self.entity_overlap_any_radio.toggled.connect(self._on_ui_value_changed)
        if self.overlap_contain_radio:
            self.overlap_contain_radio.toggled.connect(self._on_ui_value_changed)
        if self.overlap_overlap_radio:
            self.overlap_overlap_radio.toggled.connect(self._on_ui_value_changed)
        if self.model_combo:
            self.model_combo.currentIndexChanged.connect(self._on_ui_value_changed)
        if self.chunk_delimiter_edit:
            self.chunk_delimiter_edit.textChanged.connect(self._on_ui_value_changed)
        if self.chunk_max_chars_spin:
            self.chunk_max_chars_spin.valueChanged.connect(self._on_ui_value_changed)
        if self.ignore_newlines_checkbox:
            self.ignore_newlines_checkbox.toggled.connect(self._on_ui_value_changed)
        if self.ignore_whitespace_checkbox:
            self.ignore_whitespace_checkbox.toggled.connect(self._on_ui_value_changed)
        if self.ocr_opacity_slider:
            self.ocr_opacity_slider.valueChanged.connect(self._on_ui_value_changed)
        if self.ocr_before_detect_checkbox:
            self.ocr_before_detect_checkbox.toggled.connect(self._on_ui_value_changed)
        if self.ocr_auto_color_checkbox:
            self.ocr_auto_color_checkbox.toggled.connect(self._on_ui_value_changed)
        if self.ocr_offset_x_spin:
            self.ocr_offset_x_spin.valueChanged.connect(self._on_ui_value_changed)
        if self.ocr_offset_y_spin:
            self.ocr_offset_y_spin.valueChanged.connect(self._on_ui_value_changed)

    def _on_ui_value_changed(self, *_):
        if self._suspend_auto_save:
            return
        self.save_current_to_file()

    def set_enabled_entities(self, enabled_entities: List[str]):
        enabled = {str(name).strip().upper() for name in (enabled_entities or [])}
        previous = self._suspend_auto_save
        self._suspend_auto_save = True
        try:
            for entity, checkbox in self.checkboxes.items():
                checkbox.setChecked(entity in enabled)
        finally:
            self._suspend_auto_save = previous

    def get_enabled_entities(self) -> List[str]:
        result = []
        for entity in self.entity_types:
            checkbox = self.checkboxes.get(entity)
            if checkbox and checkbox.isChecked():
                result.append(entity)
        return result

    def set_duplicate_settings(self, entity_overlap_mode: str, overlap_mode: str):
        entity_mode = str(entity_overlap_mode or "any").strip().lower()
        previous = self._suspend_auto_save
        self._suspend_auto_save = True
        try:
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
        finally:
            self._suspend_auto_save = previous

    def get_duplicate_settings(self) -> Dict[str, str]:
        entity_overlap_mode = "any"
        if (
            self.entity_overlap_same_radio
            and self.entity_overlap_same_radio.isChecked()
        ):
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
        previous = self._suspend_auto_save
        self._suspend_auto_save = True
        try:
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == model_name:
                    self.model_combo.setCurrentIndex(i)
                    return
        finally:
            self._suspend_auto_save = previous

    def set_chunk_settings(self, delimiter: str, max_chars: int):
        previous = self._suspend_auto_save
        self._suspend_auto_save = True
        try:
            if self.chunk_delimiter_edit:
                if delimiter is None:
                    self.chunk_delimiter_edit.setText("。")
                else:
                    self.chunk_delimiter_edit.setText(str(delimiter))
            if self.chunk_max_chars_spin:
                clamped = min(
                    DetectConfigService.CHUNK_MAX_CHARS_MAX,
                    max(
                        DetectConfigService.CHUNK_MAX_CHARS_MIN,
                        int(max_chars or 15000),
                    ),
                )
                self.chunk_max_chars_spin.setValue(clamped)
        finally:
            self._suspend_auto_save = previous

    def get_chunk_settings(self) -> Dict[str, Any]:
        delimiter = "。"
        max_chars = 15000
        if self.chunk_delimiter_edit:
            delimiter = self.chunk_delimiter_edit.text()
        if self.chunk_max_chars_spin:
            max_chars = self.chunk_max_chars_spin.value()
        return {"delimiter": delimiter, "max_chars": max_chars}

    def set_text_preprocess_settings(
        self,
        ignore_newlines: bool,
        ignore_whitespace: bool,
    ):
        previous = self._suspend_auto_save
        self._suspend_auto_save = True
        try:
            if self.ignore_newlines_checkbox:
                self.ignore_newlines_checkbox.setChecked(bool(ignore_newlines))
            if self.ignore_whitespace_checkbox:
                self.ignore_whitespace_checkbox.setChecked(bool(ignore_whitespace))
        finally:
            self._suspend_auto_save = previous

    def get_text_preprocess_settings(self) -> Dict[str, bool]:
        ignore_newlines = True
        ignore_whitespace = False
        if self.ignore_newlines_checkbox:
            ignore_newlines = self.ignore_newlines_checkbox.isChecked()
        if self.ignore_whitespace_checkbox:
            ignore_whitespace = self.ignore_whitespace_checkbox.isChecked()
        return {
            "ignore_newlines": ignore_newlines,
            "ignore_whitespace": ignore_whitespace,
        }

    def _update_ocr_color_button(self):
        if not self.ocr_color_button:
            return
        color = QColor(*self._ocr_color)
        self.ocr_color_button.setStyleSheet(
            f"background-color: {color.name()}; color: #ffffff;"
        )
        self.ocr_color_button.setText(
            f"色を選択... ({self._ocr_color[0]}, {self._ocr_color[1]}, {self._ocr_color[2]})"
        )

    def _choose_ocr_color(self):
        if not self.ocr_color_button:
            return
        current = QColor(*self._ocr_color)
        selected = QColorDialog.getColor(current, self, "埋め込みテキスト色を選択")
        if not selected.isValid():
            return
        self._ocr_color = [selected.red(), selected.green(), selected.blue()]
        self._update_ocr_color_button()
        self._on_ui_value_changed()

    def set_ocr_settings(
        self,
        *,
        font_color: List[int],
        opacity: float,
        ocr_before_detect: bool,
        auto_color: bool = False,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ):
        previous = self._suspend_auto_save
        self._suspend_auto_save = True
        try:
            self._ocr_color = DetectConfigService._coerce_rgb_color(
                font_color,
                DetectConfigService.DEFAULT_OCR_SETTINGS["font_color"],
            )
            self._update_ocr_color_button()

            opacity_percent = int(round((1.0 - max(0.0, min(1.0, float(opacity)))) * 100))
            if self.ocr_opacity_slider:
                self.ocr_opacity_slider.setValue(opacity_percent)
            if self.ocr_before_detect_checkbox:
                self.ocr_before_detect_checkbox.setChecked(bool(ocr_before_detect))
            if self.ocr_auto_color_checkbox:
                self.ocr_auto_color_checkbox.setChecked(bool(auto_color))
            if self.ocr_offset_x_spin:
                self.ocr_offset_x_spin.setValue(
                    DetectConfigService._coerce_float(offset_x)
                )
            if self.ocr_offset_y_spin:
                self.ocr_offset_y_spin.setValue(
                    DetectConfigService._coerce_float(offset_y)
                )
        finally:
            self._suspend_auto_save = previous

    def get_ocr_settings(self) -> Dict[str, Any]:
        ocr_before_detect = False
        opacity_percent = 0

        if self.ocr_before_detect_checkbox:
            ocr_before_detect = (
                self.ocr_before_detect_checkbox.isChecked() and self._ocr_available
            )
        if self.ocr_opacity_slider:
            opacity_percent = int(self.ocr_opacity_slider.value())

        auto_color = False
        if self.ocr_auto_color_checkbox:
            auto_color = self.ocr_auto_color_checkbox.isChecked() and self._ocr_available

        offset_x = 0.0
        if self.ocr_offset_x_spin:
            offset_x = float(self.ocr_offset_x_spin.value())

        offset_y = 0.0
        if self.ocr_offset_y_spin:
            offset_y = float(self.ocr_offset_y_spin.value())

        return {
            "font_color": list(self._ocr_color),
            "opacity": max(0.0, min(1.0, 1.0 - opacity_percent / 100.0)),
            "ocr_before_detect": ocr_before_detect,
            "auto_color": auto_color,
            "offset_x": offset_x,
            "offset_y": offset_y,
        }

    def _on_select_all_clicked(self):
        checkboxes = list(self.checkboxes.values())
        if not checkboxes:
            return

        should_select_all = not all(checkbox.isChecked() for checkbox in checkboxes)
        previous = self._suspend_auto_save
        self._suspend_auto_save = True
        try:
            for checkbox in checkboxes:
                checkbox.setChecked(should_select_all)
        finally:
            self._suspend_auto_save = previous
        self._on_ui_value_changed()

    # ── ファイル監視・同期 ──

    def _start_watching(self):
        """config_pathのファイル変更監視を開始する"""
        config_str = str(self.config_path)
        self._file_watcher = QFileSystemWatcher([config_str], self)
        self._file_watcher.fileChanged.connect(self._on_config_file_changed)

    def _on_config_file_changed(self, path: str):
        """外部エディタによる設定変更を検知してUIへ反映する"""
        try:
            data = self._load_config_json()
            if data is None:
                return
            # エンティティ
            entities = data.get("enabled_entities", [])
            if isinstance(entities, list):
                self.set_enabled_entities(entities)
            # spaCyモデル
            model = data.get("spacy_model", "")
            if isinstance(model, str) and model.strip():
                self.set_spacy_model(model.strip())
            # 重複削除設定
            dup = data.get("duplicate_settings", {})
            if isinstance(dup, dict):
                self.set_duplicate_settings(
                    dup.get("entity_overlap_mode", "any"),
                    dup.get("overlap", "overlap"),
                )
            # チャンク分割設定
            chunk = data.get("chunk_settings", {})
            if isinstance(chunk, dict):
                self.set_chunk_settings(
                    chunk.get("delimiter", "。"),
                    chunk.get("max_chars", 15000),
                )
            preprocess = data.get("text_preprocess_settings", {})
            if isinstance(preprocess, dict):
                self.set_text_preprocess_settings(
                    preprocess.get("ignore_newlines", True),
                    preprocess.get("ignore_whitespace", False),
                )
            ocr_settings = data.get("ocr_settings", {})
            if isinstance(ocr_settings, dict):
                self.set_ocr_settings(
                    font_color=ocr_settings.get("font_color", [0, 0, 0]),
                    opacity=ocr_settings.get("opacity", 0.0),
                    ocr_before_detect=ocr_settings.get("ocr_before_detect", False),
                    auto_color=ocr_settings.get("auto_color", False),
                    offset_x=ocr_settings.get("offset_x", 0.0),
                    offset_y=ocr_settings.get("offset_y", 0.0),
                )
        except Exception as exc:
            logger.warning(f"設定ファイルの変更反映に失敗: {exc}")
        finally:
            # 一部OSではファイル変更後に監視が外れるため再登録
            if self._file_watcher and path not in self._file_watcher.files():
                self._file_watcher.addPath(path)

    def save_current_to_file(self) -> bool:
        """ダイアログ上の現在の状態を設定ファイルへ書き出す"""
        try:
            data: Dict[str, Any] = {}
            if self.config_path.exists():
                text = self.config_path.read_text(encoding="utf-8")
                loaded = json.loads(text or "{}")
                if isinstance(loaded, dict):
                    data = loaded
            data["enabled_entities"] = self.get_enabled_entities()
            dup = self.get_duplicate_settings()
            data["duplicate_settings"] = dup
            model = self.get_spacy_model()
            if model:
                data["spacy_model"] = model
            data["chunk_settings"] = self.get_chunk_settings()
            data["text_preprocess_settings"] = self.get_text_preprocess_settings()
            data["ocr_settings"] = self.get_ocr_settings()
            # 書き込み中は監視を一時停止して自己トリガーを防ぐ
            config_str = str(self.config_path)
            if self._file_watcher:
                self._file_watcher.removePath(config_str)
            text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            self.config_path.write_text(text, encoding="utf-8")
            if self._file_watcher:
                self._file_watcher.addPath(config_str)
            return True
        except Exception as exc:
            logger.warning(f"ダイアログ状態の設定ファイル保存に失敗: {exc}")
            return False

    def _load_config_json(self) -> Optional[Dict[str, Any]]:
        """config_pathからJSONを読み込む（失敗時None）"""
        try:
            if not self.config_path.exists():
                return None
            text = self.config_path.read_text(encoding="utf-8")
            data = json.loads(text or "{}")
            return data if isinstance(data, dict) else None
        except Exception:
            return None
