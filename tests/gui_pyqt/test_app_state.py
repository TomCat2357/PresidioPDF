import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.gui_pyqt.models.app_state import AppState


def _make_app():
    return QApplication.instance() or QApplication([])


def test_reset_results_emits_signals_even_when_already_none():
    """値が既にNoneでも、reset_resultsは必ず各resultのchangedシグナルを発火する。

    通常のsetter（例: detect_result = None）は「値が変化した場合のみ」
    シグナルを発火するため、Detectを一度も実行していない（＝既にNone）状態で
    PDFを切り替えても、setterへのNone代入だけでは購読側（ResultPanel等）に
    通知が届かず、前のPDFの手動マークが残ってしまう。reset_resultsはこの
    ケースでも必ず通知することを保証する。
    """
    _make_app()
    state = AppState()
    assert state.read_result is None
    assert state.detect_result is None
    assert state.duplicate_result is None
    assert state.ocr_result is None

    received = {"read": [], "detect": [], "duplicate": [], "ocr": []}
    state.read_result_changed.connect(lambda v: received["read"].append(v))
    state.detect_result_changed.connect(lambda v: received["detect"].append(v))
    state.duplicate_result_changed.connect(lambda v: received["duplicate"].append(v))
    state.ocr_result_changed.connect(lambda v: received["ocr"].append(v))

    # 全てのresultが既にNoneの状態でreset_resultsを呼んでも、必ず1回ずつ通知される
    state.reset_results()

    assert received["read"] == [None]
    assert received["detect"] == [None]
    assert received["duplicate"] == [None]
    assert received["ocr"] == [None]


def test_reset_results_clears_values_that_were_set():
    _make_app()
    state = AppState()
    state.read_result = {"detect": []}
    state.detect_result = {"detect": ["dummy"]}
    state.duplicate_result = {"detect": ["dummy"]}
    state.ocr_result = {"embedded_count": 1}

    state.reset_results()

    assert state.read_result is None
    assert state.detect_result is None
    assert state.duplicate_result is None
    assert state.ocr_result is None


def test_clear_uses_reset_results_and_notifies_even_when_already_empty():
    """clear()もreset_resultsを経由し、既に空の状態でも確実に通知が飛ぶこと。"""
    _make_app()
    state = AppState()

    detect_events = []
    state.detect_result_changed.connect(lambda v: detect_events.append(v))

    # 何もセットしていない（全てNone）状態でclear()しても通知が飛ぶこと
    state.clear()

    assert detect_events == [None]
    assert state.pdf_path is None
    assert state.status_message == "準備完了"
