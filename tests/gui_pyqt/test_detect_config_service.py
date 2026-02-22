import json
import copy
import re
from types import SimpleNamespace

from src.gui_pyqt.services.detect_config_service import DetectConfigService
from src.gui_pyqt.services.pipeline_service import PipelineService
from src.gui_pyqt.views.main_window import MainWindow


def _write_config(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_config(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_spacy_models_order_and_default():
    assert DetectConfigService.SPACY_MODELS == [
        "ja_core_news_sm",
        "ja_core_news_md",
        "ja_core_news_lg",
        "ja_core_news_trf",
        "ja_ginza",
        "ja_ginza_electra",
    ]
    assert DetectConfigService.DEFAULT_SPACY_MODEL == "ja_core_news_sm"


def test_config_path_is_under_presidio_directory(tmp_path):
    service = DetectConfigService(tmp_path)
    assert service.config_path == tmp_path / ".presidio" / "config.json"


def test_add_entity_preserves_unknown_japanese_keys(tmp_path):
    service = DetectConfigService(tmp_path)
    config_path = service.config_path
    _write_config(
        config_path,
        {
            "spacy_model": "ja_core_news_trf",
            "enabled_entities": ["PERSON", "LOCATION"],
            "add_entity": {
                "PERSON": ["山田太郎"],
                "address": ["渋谷区神南"],
                "固有名詞": ["東京タワー"],
                "ほげほげ": ["テスト語"],
            },
            "ommit_entity": [],
            "duplicate_settings": {"entity_overlap_mode": "any", "overlap": "overlap"},
        },
    )

    service.ensure_config_file()
    normalized = _read_config(config_path)
    add_entity = normalized.get("add_entity", {})

    assert add_entity.get("LOCATION") == ["渋谷区神南"]
    assert add_entity.get("固有名詞") == ["東京タワー"]
    assert add_entity.get("ほげほげ") == ["テスト語"]


def test_explicit_empty_enabled_entities_is_preserved(tmp_path):
    service = DetectConfigService(tmp_path)
    config_path = service.config_path
    _write_config(
        config_path,
        {
            "enabled_entities": [],
        },
    )

    loaded = service.ensure_config_file()
    normalized = _read_config(config_path)

    assert loaded == []
    assert normalized.get("enabled_entities") == []


def test_save_operations_do_not_drop_unknown_add_entity_keys(tmp_path):
    service = DetectConfigService(tmp_path)
    config_path = service.config_path
    _write_config(
        config_path,
        {
            "spacy_model": "ja_core_news_trf",
            "enabled_entities": ["PERSON"],
            "add_entity": {
                "PERSON": ["田中"],
                "固有名詞": ["東京スカイツリー"],
                "ほげほげ": ["あいうえお"],
            },
            "ommit_entity": [],
            "duplicate_settings": {"entity_overlap_mode": "any", "overlap": "overlap"},
        },
    )

    service.save_enabled_entities(["PERSON", "LOCATION"])
    service.save_duplicate_settings(entity_overlap_mode="same", overlap="contain")

    updated = _read_config(config_path)
    add_entity = updated.get("add_entity", {})
    assert add_entity.get("固有名詞") == ["東京スカイツリー"]
    assert add_entity.get("ほげほげ") == ["あいうえお"]

    add_patterns, omit_patterns = service.load_custom_patterns()
    assert ("固有名詞", "東京スカイツリー") in add_patterns
    assert ("ほげほげ", "あいうえお") in add_patterns
    assert omit_patterns == []


def test_add_pattern_known_entity_enabled_only():
    resolved = PipelineService._resolve_add_pattern_entity(
        "PERSON",
        ["PERSON", "LOCATION"],
    )
    assert resolved == "PERSON"


def test_add_pattern_alias_requires_enabled_entity():
    disabled = PipelineService._resolve_add_pattern_entity("PEARSON", ["LOCATION"])
    enabled = PipelineService._resolve_add_pattern_entity("PEARSON", ["PERSON"])
    assert disabled is None
    assert enabled == "PERSON"


def test_add_pattern_unknown_entity_always_enabled():
    resolved = PipelineService._resolve_add_pattern_entity(
        "MUHO",
        ["PERSON"],
    )
    assert resolved == "MUHO"


def test_build_detect_target_text_newline_ignored_is_backward_compatible():
    text_2d = [["AB", "CD"], ["EF"]]

    target, spans, base_length = PipelineService._build_detect_target_text(
        text_2d=text_2d,
        ignore_newlines=True,
        ignore_whitespace=False,
    )

    assert target == "ABCDEF"
    assert base_length == 6
    assert spans == [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]
    assert PipelineService._map_target_span_to_base_offsets(1, 4, spans, base_length) == (
        1,
        4,
    )


def test_build_detect_target_text_inserts_newline_when_disabled():
    text_2d = [["AB", "CD"], ["EF"]]

    target, spans, base_length = PipelineService._build_detect_target_text(
        text_2d=text_2d,
        ignore_newlines=False,
        ignore_whitespace=False,
    )

    assert target == "AB\nCD\nEF"
    assert base_length == 6
    assert spans[2] == (2, 2)  # block境界の挿入改行
    assert spans[5] == (4, 4)  # page境界の挿入改行
    assert PipelineService._map_target_span_to_base_offsets(3, 5, spans, base_length) == (
        2,
        4,
    )


def test_build_detect_target_text_whitespace_ignored_uses_original_offsets():
    text_2d = [["A B", " C"], ["D\tE"]]

    target, spans, base_length = PipelineService._build_detect_target_text(
        text_2d=text_2d,
        ignore_newlines=True,
        ignore_whitespace=True,
    )

    assert target == "ABCDE"
    assert base_length == 8
    assert spans == [(0, 1), (2, 3), (4, 5), (5, 6), (7, 8)]
    assert PipelineService._map_target_span_to_base_offsets(1, 4, spans, base_length) == (
        2,
        6,
    )


def test_build_detect_target_text_both_options_on_and_off_interaction():
    text_2d = [["AB", "CD"], ["EF"]]

    target, spans, base_length = PipelineService._build_detect_target_text(
        text_2d=text_2d,
        ignore_newlines=False,
        ignore_whitespace=True,
    )

    assert target == "ABCDEF"
    assert base_length == 6
    assert spans == [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]


def test_chunk_settings_allow_empty_delimiter(tmp_path):
    service = DetectConfigService(tmp_path)
    service.ensure_config_file()

    saved = service.save_chunk_settings("", 1200)
    loaded = service.load_chunk_settings()

    assert saved["delimiter"] == ""
    assert loaded["delimiter"] == ""
    assert loaded["max_chars"] == 1200


def test_add_omit_patterns_appends_without_duplicates(tmp_path):
    service = DetectConfigService(tmp_path)
    service.ensure_config_file()

    pattern = DetectConfigService.build_exact_word_pattern("山田")
    service.add_omit_patterns([pattern, pattern])
    _, omit_patterns = service.load_custom_patterns()

    assert omit_patterns.count(pattern) == 1


def test_text_preprocess_settings_default_values(tmp_path):
    service = DetectConfigService(tmp_path)
    loaded = service.ensure_config_file()
    assert isinstance(loaded, list)

    settings = service.load_text_preprocess_settings()
    assert settings == {
        "ignore_newlines": True,
        "ignore_whitespace": False,
    }

    normalized = _read_config(service.config_path)
    assert normalized.get("text_preprocess_settings") == {
        "ignore_newlines": True,
        "ignore_whitespace": False,
    }


def test_text_preprocess_settings_save_and_load(tmp_path):
    service = DetectConfigService(tmp_path)
    service.ensure_config_file()

    saved = service.save_text_preprocess_settings(
        ignore_newlines=False,
        ignore_whitespace=True,
    )
    loaded = service.load_text_preprocess_settings()

    assert saved == {
        "ignore_newlines": False,
        "ignore_whitespace": True,
    }
    assert loaded == saved


def test_text_preprocess_settings_are_normalized_when_missing(tmp_path):
    service = DetectConfigService(tmp_path)
    _write_config(
        service.config_path,
        {
            "enabled_entities": ["PERSON"],
            "text_preprocess_settings": {},
        },
    )

    service.ensure_config_file()
    normalized = _read_config(service.config_path)
    assert normalized.get("text_preprocess_settings") == {
        "ignore_newlines": True,
        "ignore_whitespace": False,
    }


def test_add_add_patterns_appends_and_keeps_unknown_keys(tmp_path):
    service = DetectConfigService(tmp_path)
    config_path = service.config_path
    _write_config(
        config_path,
        {
            "spacy_model": "ja_core_news_sm",
            "enabled_entities": ["PERSON"],
            "add_entity": {
                "固有名詞": ["東京タワー"],
            },
            "ommit_entity": [],
            "duplicate_settings": {"entity_overlap_mode": "any", "overlap": "overlap"},
        },
    )

    pattern = DetectConfigService.build_exact_word_pattern("山田")
    service.add_add_patterns([("PEARSON", pattern), ("固有名詞", "大阪城")])
    data = _read_config(config_path)
    add_entity = data.get("add_entity", {})

    assert pattern in add_entity.get("PERSON", [])
    assert add_entity.get("固有名詞") == ["東京タワー", "大阪城"]


def test_build_exact_word_pattern_matches_exact_only():
    pattern = DetectConfigService.build_exact_word_pattern("山田")
    regex = re.compile(pattern)

    assert regex.search("山田です")
    assert regex.search("  山田  ")
    assert regex.search("（山田）")
    assert regex.search("山田")
    assert regex.search("山田。")
    assert not regex.search("大山田")


def test_build_detect_list_csv_rows_formats_columns():
    detect_list = [
        {
            "word": "山田",
            "entity": "PERSON",
            "origin": "auto",
            "start": {"page_num": 0, "block_num": 0, "offset": 0},
            "end": {"page_num": 0, "block_num": 0, "offset": 1},
        },
        {
            "word": "渋谷",
            "entity": "LOCATION",
            "origin": "manual",
            "manual": True,
            "start": {"page_num": 1, "block_num": 2, "offset": 10},
            "end": {"page_num": 1, "block_num": 2, "offset": 11},
        },
    ]

    rows = MainWindow._build_detect_list_csv_rows(detect_list)

    assert rows == [
        ["1", "人名", "山田", "p1:b1:1", ""],
        ["2", "場所", "渋谷", "p2:b3:11", "✓"],
    ]


def test_remove_add_patterns_by_words_removes_all_entities(tmp_path):
    service = DetectConfigService(tmp_path)
    config_path = service.config_path
    tanaka_pattern = DetectConfigService.build_exact_word_pattern("田中")
    yamada_pattern = DetectConfigService.build_exact_word_pattern("山田")
    _write_config(
        config_path,
        {
            "spacy_model": "ja_core_news_sm",
            "enabled_entities": ["PERSON", "LOCATION"],
            "add_entity": {
                "PERSON": [tanaka_pattern, "田中", yamada_pattern],
                "LOCATION": [tanaka_pattern],
            },
            "ommit_entity": [],
            "duplicate_settings": {"entity_overlap_mode": "any", "overlap": "overlap"},
        },
    )

    service.remove_add_patterns_by_words(["田中"])
    data = _read_config(config_path)
    add_entity = data.get("add_entity", {})

    assert add_entity.get("PERSON") == [yamada_pattern]
    assert add_entity.get("LOCATION") == []


def test_remove_omit_patterns_by_words_removes_exact_word_and_pattern(tmp_path):
    service = DetectConfigService(tmp_path)
    config_path = service.config_path
    tanaka_pattern = DetectConfigService.build_exact_word_pattern("田中")
    yamada_pattern = DetectConfigService.build_exact_word_pattern("山田")
    _write_config(
        config_path,
        {
            "spacy_model": "ja_core_news_sm",
            "enabled_entities": ["PERSON"],
            "add_entity": {"PERSON": []},
            "ommit_entity": [tanaka_pattern, "田中", yamada_pattern],
            "duplicate_settings": {"entity_overlap_mode": "any", "overlap": "overlap"},
        },
    )

    updated = service.remove_omit_patterns_by_words(["田中"])
    assert updated == [yamada_pattern]


def test_normalize_config_data_deduplicates_same_word_entries(tmp_path):
    service = DetectConfigService(tmp_path)
    config_path = service.config_path
    _write_config(
        config_path,
        {
            "spacy_model": "ja_core_news_sm",
            "enabled_entities": ["PERSON", "LOCATION"],
            "add_entity": {
                "PEARSON": ["田中", "田中"],
                "LOCATION": ["田中", "田中"],
            },
            "ommit_entity": ["山田", "山田"],
            "duplicate_settings": {"entity_overlap_mode": "any", "overlap": "overlap"},
        },
    )

    service.ensure_config_file()
    normalized = _read_config(config_path)
    add_entity = normalized.get("add_entity", {})

    assert add_entity.get("PERSON") == ["田中"]
    assert add_entity.get("LOCATION") == ["田中"]
    assert normalized.get("ommit_entity") == ["山田"]


class _MainWindowExactMatchDouble:
    def __init__(self, text_2d):
        self.detect_config_service = DetectConfigService()
        self.app_state = SimpleNamespace(read_result=None)
        self._source_result = {"text": text_2d}
        self.messages = []

    def _get_current_result(self):
        return self._source_result

    def _extract_text_2d_from_result(self, result):
        return MainWindow._extract_text_2d_from_result(result)

    def _build_span_key_from_positions(self, start_pos, end_pos):
        return MainWindow._build_span_key_from_positions(start_pos, end_pos)

    def _normalize_runtime_entity_name(self, entity_name):
        return MainWindow._normalize_runtime_entity_name(entity_name)

    def log_message(self, message):
        self.messages.append(message)


def test_build_exact_match_entities_skips_same_entity_and_same_span():
    fake = _MainWindowExactMatchDouble([["田中"]])
    current_entities = [
        {
            "word": "田中",
            "entity": "PERSON",
            "start": {"page_num": 0, "block_num": 0, "offset": 0},
            "end": {"page_num": 0, "block_num": 0, "offset": 1},
        }
    ]
    snapshot = copy.deepcopy(current_entities)

    new_entities = MainWindow._build_exact_match_entities(
        fake,
        [("田中", "PEARSON")],
        current_entities,
    )

    assert new_entities == []
    assert current_entities == snapshot


def test_build_exact_match_entities_allows_different_entity_same_span():
    fake = _MainWindowExactMatchDouble([["田中"]])
    current_entities = [
        {
            "word": "田中",
            "entity": "LOCATION",
            "start": {"page_num": 0, "block_num": 0, "offset": 0},
            "end": {"page_num": 0, "block_num": 0, "offset": 1},
        }
    ]

    new_entities = MainWindow._build_exact_match_entities(
        fake,
        [("田中", "PERSON")],
        current_entities,
    )

    assert len(new_entities) == 1
    assert new_entities[0]["word"] == "田中"
    assert new_entities[0]["entity"] == "PERSON"
    assert new_entities[0]["start"] == {"page_num": 0, "block_num": 0, "offset": 0}
    assert new_entities[0]["end"] == {"page_num": 0, "block_num": 0, "offset": 1}


def test_dedupe_detect_by_entity_and_span_skips_complete_matches():
    detect_list = [
        {
            "word": "田中",
            "entity": "PERSON",
            "start": {"page_num": 0, "block_num": 0, "offset": 0},
            "end": {"page_num": 0, "block_num": 0, "offset": 1},
            "origin": "auto",
        },
        {
            "word": "田中太郎",
            "entity": "PERSON",
            "start": {"page_num": 0, "block_num": 0, "offset": 0},
            "end": {"page_num": 0, "block_num": 0, "offset": 1},
            "origin": "custom",
        },
    ]

    deduped = PipelineService._dedupe_detect_by_entity_and_span(detect_list)

    assert len(deduped) == 1
    assert deduped[0]["word"] == "田中"
    assert deduped[0]["origin"] == "auto"


def test_dedupe_detect_by_entity_and_span_keeps_different_entity_same_span():
    detect_list = [
        {
            "word": "田中",
            "entity": "PERSON",
            "start": {"page_num": 0, "block_num": 0, "offset": 0},
            "end": {"page_num": 0, "block_num": 0, "offset": 1},
        },
        {
            "word": "田中",
            "entity": "LOCATION",
            "start": {"page_num": 0, "block_num": 0, "offset": 0},
            "end": {"page_num": 0, "block_num": 0, "offset": 1},
        },
    ]

    deduped = PipelineService._dedupe_detect_by_entity_and_span(detect_list)

    assert len(deduped) == 2
    assert deduped[0]["entity"] == "PERSON"
    assert deduped[1]["entity"] == "LOCATION"


class _ResultPanelDetectInputDouble:
    def __init__(self, entities):
        self._entities = entities

    def get_entities(self):
        return self._entities


class _MainWindowDetectInputDouble:
    def __init__(self, read_result, panel_entities):
        self.app_state = SimpleNamespace(read_result=read_result)
        self.result_panel = _ResultPanelDetectInputDouble(panel_entities)
        self.messages = []

    def log_message(self, message):
        self.messages.append(message)


def test_build_read_result_for_detect_uses_current_panel_entities():
    read_result = {
        "metadata": {"pdf": {"path": "/tmp/sample.pdf"}},
        "text": [["dummy"]],
        "detect": [
            {
                "word": "旧検出",
                "entity": "PERSON",
                "start": {"page_num": 0, "block_num": 0, "offset": 0},
                "end": {"page_num": 0, "block_num": 0, "offset": 1},
            }
        ],
    }
    panel_entities = [
        {
            "word": "既存1",
            "entity": "PERSON",
            "start": {"page_num": 0, "block_num": 0, "offset": 1},
            "end": {"page_num": 0, "block_num": 0, "offset": 2},
        },
        {
            "word": "既存2",
            "entity": "LOCATION",
            "start": {"page_num": 0, "block_num": 0, "offset": 3},
            "end": {"page_num": 0, "block_num": 0, "offset": 4},
        },
    ]
    fake = _MainWindowDetectInputDouble(read_result, panel_entities)

    result = MainWindow._build_read_result_for_detect(fake)

    assert result["detect"] == panel_entities
    assert result["detect"] is not panel_entities
    assert any("既存検出 2件を保持してDetectを実行します" in msg for msg in fake.messages)


class _ResultPanelPreviewClickDouble:
    def __init__(self, entities):
        self.entities = entities
        self.selected_rows = []
        self.focused = False

    def select_row(self, row):
        self.selected_rows.append(row)

    def focus_results_table(self):
        self.focused = True


class _MainWindowPreviewClickDouble:
    def __init__(self):
        self._all_preview_entities = [
            {
                "text": "田中",
                "entity_type": "PERSON",
                "page_num": 0,
                "block_num": 0,
                "offset": 0,
            }
        ]
        self.result_panel = _ResultPanelPreviewClickDouble(
            [
                {
                    "word": "田中",
                    "entity": "PERSON",
                    "start": {"page_num": 0, "block_num": 0, "offset": 0},
                    "end": {"page_num": 0, "block_num": 0, "offset": 1},
                }
            ]
        )


def test_on_preview_entity_clicked_moves_focus_to_result_table():
    fake = _MainWindowPreviewClickDouble()

    MainWindow.on_preview_entity_clicked(fake, 0)

    assert fake.result_panel.selected_rows == [0]
    assert fake.result_panel.focused is True
