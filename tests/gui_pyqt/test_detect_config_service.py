import json

from src.gui_pyqt.services.detect_config_service import DetectConfigService
from src.gui_pyqt.services.pipeline_service import PipelineService


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
