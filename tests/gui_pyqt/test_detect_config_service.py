import json
import re

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
