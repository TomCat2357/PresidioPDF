"""回帰テスト: Detectを一度も実行せず手動マークだけした状態でも
「保存」メニューの マスク / アノテーション付き / 検出結果一覧(CSV) が
使えること。

以前のバグ:
    update_action_states() は _get_export_source_result() を使って
    これら3項目の有効/無効を決めていたが、同ヘルパーは
    duplicate_result / detect_result しか見ず read_result を無視していた。
    そのため「Read済み・Detect未実行・手動マークのみ」の状態では
    3項目がグレーアウトして操作できなかった
    （画像系の セキュアマスク保存 / マーク は read_result へ
    フォールバックする別ヘルパーを使うため有効だった）。

方針:
    有効化条件は「結果が存在するか」まで緩め、対象0件のときは
    各 on_* ハンドラ側の実行時ガードで理由を案内する。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PyQt6.QtWidgets import QApplication

import src.gui_pyqt.views.main_window as main_window_module
from src.gui_pyqt.models.app_state import AppState
from src.gui_pyqt.views.main_window import MainWindow

from tests.gui_pyqt.test_pdf_switch_clears_manual_marks import (
    _FakeDetectConfigService,
    _make_entity,
    _create_pdf,
)


class _RecordingMessageBox:
    """QMessageBox.warning / .critical の呼び出しを記録するだけの差し替え。"""

    def __init__(self):
        self.warnings = []
        self.criticals = []

    def warning(self, _parent, _title, text, *args, **kwargs):
        self.warnings.append(text)
        return None

    def critical(self, _parent, _title, text, *args, **kwargs):
        self.criticals.append(text)
        return None


def _new_window(monkeypatch):
    monkeypatch.setattr(
        "src.gui_pyqt.views.main_window.DetectConfigService",
        _FakeDetectConfigService,
    )
    window = MainWindow(AppState())
    monkeypatch.setattr(window, "_load_mapping_for_pdf", lambda _p: False)
    monkeypatch.setattr(window, "_auto_read", lambda: None)
    return window


def _read_result(pdf_path, entities):
    return {
        "metadata": {"pdf": {"path": str(pdf_path)}},
        "text": [["本文サンプル"]],
        "detect": list(entities),
        "offset2coordsMap": {},
    }


def test_export_actions_enabled_after_read_without_detect(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    pdf_path = tmp_path / "sample.pdf"
    _create_pdf(pdf_path, "本文サンプル")

    window = _new_window(monkeypatch)
    try:
        window.show()
        window._open_pdf_path(pdf_path)
        app.processEvents()

        # Read結果のみ（Detect未実行・手動マークまだ0件）
        window.app_state.read_result = _read_result(pdf_path, [])
        app.processEvents()

        window.update_action_states()

        # 3項目とも「有効」であること（バグ時はここが False）
        assert window.export_mask_action.isEnabled()
        assert window.export_annotations_action.isEnabled()
        assert window.export_detect_list_csv_action.isEnabled()
        assert window.export_button.isEnabled()
        # 画像系との対称性
        assert window.export_mask_as_image_action.isEnabled()
        assert window.export_marked_as_image_action.isEnabled()
    finally:
        window._set_dirty(False)
        window.close()


def test_export_actions_disabled_without_pdf(monkeypatch, tmp_path):
    """PDFを開いた後で閉じると、PDF依存の前提が外れて3項目が無効へ戻る。"""
    app = QApplication.instance() or QApplication([])
    pdf_path = tmp_path / "sample.pdf"
    _create_pdf(pdf_path, "本文サンプル")

    window = _new_window(monkeypatch)
    try:
        window.show()
        window._open_pdf_path(pdf_path)
        window.app_state.read_result = _read_result(pdf_path, [])
        app.processEvents()
        window.update_action_states()
        assert window.export_mask_action.isEnabled()

        window.on_close_pdf()
        app.processEvents()
        window.update_action_states()
        assert not window.export_mask_action.isEnabled()
        assert not window.export_annotations_action.isEnabled()
        assert not window.export_detect_list_csv_action.isEnabled()
    finally:
        window._set_dirty(False)
        window.close()


def test_on_mask_warns_when_no_targets(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    pdf_path = tmp_path / "sample.pdf"
    _create_pdf(pdf_path, "本文サンプル")

    window = _new_window(monkeypatch)
    box = _RecordingMessageBox()
    monkeypatch.setattr(main_window_module, "QMessageBox", box)
    started = []
    monkeypatch.setattr(
        window.task_runner, "start_task", lambda *a, **k: started.append((a, k))
    )
    try:
        window.show()
        window._open_pdf_path(pdf_path)
        window.app_state.read_result = _read_result(pdf_path, [])
        app.processEvents()

        window.on_mask()

        assert started == []
        assert any("マスク対象がありません" in msg for msg in box.warnings)
    finally:
        window._set_dirty(False)
        window.close()


def test_on_export_annotations_warns_when_no_targets(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    pdf_path = tmp_path / "sample.pdf"
    _create_pdf(pdf_path, "本文サンプル")

    window = _new_window(monkeypatch)
    box = _RecordingMessageBox()
    monkeypatch.setattr(main_window_module, "QMessageBox", box)
    started = []
    monkeypatch.setattr(
        window.task_runner, "start_task", lambda *a, **k: started.append((a, k))
    )
    try:
        window.show()
        window._open_pdf_path(pdf_path)
        window.app_state.read_result = _read_result(pdf_path, [])
        app.processEvents()

        window.on_export_annotations()

        assert started == []
        assert any("アノテーション対象がありません" in msg for msg in box.warnings)
    finally:
        window._set_dirty(False)
        window.close()


def test_on_mask_runs_with_manual_marks_from_read_result(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    pdf_path = tmp_path / "sample.pdf"
    _create_pdf(pdf_path, "本文サンプル")

    window = _new_window(monkeypatch)
    box = _RecordingMessageBox()
    monkeypatch.setattr(main_window_module, "QMessageBox", box)
    monkeypatch.setattr(
        window, "_select_output_pdf_path", lambda *a, **k: tmp_path / "out.pdf"
    )
    captured = {}
    monkeypatch.setattr(
        window.task_runner,
        "start_task",
        lambda func, *a, **k: captured.update(func=func, args=a, kwargs=k),
    )
    try:
        window.show()
        window._open_pdf_path(pdf_path)
        manual = _make_entity("手動マーク", 0, 0, 0)
        window.app_state.read_result = _read_result(pdf_path, [manual])
        app.processEvents()

        window.on_mask()

        assert box.warnings == []
        assert captured, "start_task が呼ばれていない"
        passed_result = captured["args"][0]
        assert passed_result.get("detect") == [manual]
        assert "text" in passed_result
    finally:
        window._set_dirty(False)
        window.close()
