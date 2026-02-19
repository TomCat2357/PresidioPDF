"""
PresidioPDF PyQt - 検出設定(config.json)管理

- $HOME/.presidio/config.json を読み込み
- 未存在時は自動生成
- インポート/エクスポートを提供
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DetectConfigService:
    """GUI用検出設定の管理サービス"""

    CONFIG_DIR_NAME = ".presidio"
    CONFIG_FILE_NAME = "config.json"
    DISPLAY_FILE_NAME = "config.toml"
    SPACY_MODELS = [
        "ja_core_news_sm",
        "ja_core_news_md",
        "ja_core_news_lg",
        "ja_core_news_trf",
        "ja_ginza",
        "ja_ginza_electra",
    ]
    DEFAULT_SPACY_MODEL = "ja_core_news_sm"
    ENTITY_TYPES = [
        "PERSON",
        "LOCATION",
        "DATE_TIME",
        "PHONE_NUMBER",
        "INDIVIDUAL_NUMBER",
        "YEAR",
        "PROPER_NOUN",
        "OTHER",
    ]
    ENTITY_ALIASES = {
        "ADDRESS": "LOCATION",
        "PEARSON": "PERSON",
    }
    DUPLICATE_ENTITY_OVERLAP_MODES = ["same", "any"]
    DUPLICATE_OVERLAP_MODES = ["contain", "overlap"]
    DEFAULT_DUPLICATE_SETTINGS = {
        "entity_overlap_mode": "any",
        "overlap": "overlap",
    }

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else Path.home()
        self.config_path = self.base_dir / self.CONFIG_DIR_NAME / self.CONFIG_FILE_NAME

    def ensure_config_file(self) -> List[str]:
        """設定ファイルを保証し、有効エンティティ一覧を返す"""
        try:
            if not self.config_path.exists():
                self._write_json(self._default_json_config())
            else:
                # 既存JSONがあれば、必要キーを補完した正規化データで保存し直す
                normalized_data = self._normalize_config_data(self._load_json(self.config_path))
                self._write_json(normalized_data)
            return self._extract_enabled_entities(self._load_json(self.config_path))
        except Exception as exc:
            logger.warning(f"設定ファイル初期化に失敗: {self.config_path} ({exc})")
            fallback = self._default_json_config()
            self._write_json(fallback)
            return list(fallback.get("enabled_entities", list(self.ENTITY_TYPES)))

    def ensure_json_config_file(self) -> Path:
        """互換: config.json の存在を保証してパスを返す"""
        self.ensure_config_file()
        return self.config_path

    def load_enabled_entities(self) -> List[str]:
        """設定ファイル(config.json)から有効エンティティ一覧を読み込む"""
        if not self.config_path.exists():
            return list(self.ENTITY_TYPES)

        try:
            data = self._load_json(self.config_path)
            return self._extract_enabled_entities(data)
        except Exception as exc:
            logger.warning(f"設定ファイルの読み込みに失敗: {self.config_path} ({exc})")
            return list(self.ENTITY_TYPES)

    def save_enabled_entities(self, entities: List[str]) -> List[str]:
        """有効エンティティ一覧を config.json へ保存（他設定は保持）"""
        normalized = self._normalize_entities(entities)
        data = self._load_json(self.config_path) if self.config_path.exists() else {}
        if not isinstance(data, dict):
            data = {}
        data = self._normalize_config_data(data)
        data["enabled_entities"] = normalized
        self._write_json(data)
        return normalized

    def load_spacy_model(self) -> str:
        """設定ファイルからspaCyモデル名を読み込む"""
        if not self.config_path.exists():
            return self.DEFAULT_SPACY_MODEL
        try:
            data = self._load_json(self.config_path)
            if isinstance(data, dict):
                model = data.get("spacy_model", self.DEFAULT_SPACY_MODEL)
                if isinstance(model, str) and model.strip():
                    return model.strip()
        except Exception as exc:
            logger.warning(f"spaCyモデル設定の読み込みに失敗: {exc}")
        return self.DEFAULT_SPACY_MODEL

    def save_spacy_model(self, model_name: str) -> str:
        """spaCyモデル名を設定ファイルに保存する"""
        name = str(model_name or "").strip()
        if not name:
            name = self.DEFAULT_SPACY_MODEL
        data = self._load_json(self.config_path) if self.config_path.exists() else {}
        if not isinstance(data, dict):
            data = {}
        data = self._normalize_config_data(data)
        data["spacy_model"] = name
        self._write_json(data)
        return name

    @classmethod
    def get_installed_spacy_models(cls) -> List[str]:
        """インストール済みのspaCyモデル一覧を返す"""
        try:
            import spacy.util
        except Exception as exc:
            logger.warning(f"spaCyの状態確認に失敗: {exc}")
            return []

        installed = []
        for model in cls.SPACY_MODELS:
            try:
                if spacy.util.is_package(model):
                    installed.append(model)
            except Exception as exc:
                logger.warning(f"spaCyモデル確認失敗: {model} ({exc})")
        return installed

    def load_duplicate_settings(self) -> Dict[str, str]:
        """重複削除設定を読み込む"""
        self.ensure_config_file()
        try:
            data = self._normalize_config_data(self._load_json(self.config_path))
            self._write_json(data)
            settings = data.get("duplicate_settings", {})
            if isinstance(settings, dict):
                return {
                    "entity_overlap_mode": str(
                        settings.get(
                            "entity_overlap_mode",
                            self.DEFAULT_DUPLICATE_SETTINGS["entity_overlap_mode"],
                        )
                    ),
                    "overlap": str(
                        settings.get(
                            "overlap",
                            self.DEFAULT_DUPLICATE_SETTINGS["overlap"],
                        )
                    ),
                }
        except Exception as exc:
            logger.warning(f"重複設定の読み込みに失敗: {self.config_path} ({exc})")
        return dict(self.DEFAULT_DUPLICATE_SETTINGS)

    def save_duplicate_settings(
        self,
        entity_overlap_mode: str,
        overlap: str,
    ) -> Dict[str, str]:
        """重複削除設定を保存する"""
        data = self._load_json(self.config_path) if self.config_path.exists() else {}
        if not isinstance(data, dict):
            data = {}
        data = self._normalize_config_data(data)
        data["duplicate_settings"] = self._extract_duplicate_settings(
            {
                "duplicate_settings": {
                    "entity_overlap_mode": entity_overlap_mode,
                    "overlap": overlap,
                }
            }
        )
        self._write_json(data)
        return dict(data["duplicate_settings"])

    def load_last_directory(self, key: str) -> str:
        """最後に使用したディレクトリパスを返す（存在しなければ空文字列）"""
        try:
            if self.config_path.exists():
                data = self._load_json(self.config_path)
                if isinstance(data, dict):
                    last_dirs = data.get("last_directories", {})
                    if isinstance(last_dirs, dict):
                        return str(last_dirs.get(key, "") or "")
        except Exception as exc:
            logger.warning(f"last_directories の読み込みに失敗: {exc}")
        return ""

    def save_last_directory(self, key: str, directory: str) -> None:
        """最後に使用したディレクトリパスを config.json に保存する"""
        try:
            data = self._load_json(self.config_path) if self.config_path.exists() else {}
            if not isinstance(data, dict):
                data = {}
            last_dirs = data.get("last_directories", {})
            if not isinstance(last_dirs, dict):
                last_dirs = {}
            last_dirs[key] = str(directory or "")
            data["last_directories"] = last_dirs
            self._write_json(data)
        except Exception as exc:
            logger.warning(f"last_directories の保存に失敗: {exc}")

    def import_from(self, source_path: Path) -> List[str]:
        """外部JSONを読み込み、$HOME/.presidio/config.jsonへ反映"""
        data = self._load_json(Path(source_path))
        normalized_data = self._normalize_config_data(data)
        self._write_json(normalized_data)
        return list(normalized_data.get("enabled_entities", list(self.ENTITY_TYPES)))

    def export_to(self, output_path: Path) -> Path:
        """$HOME/.presidio/config.jsonを指定先へ出力"""
        if not self.config_path.exists():
            self._write_json(self._default_json_config())

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.config_path, output_path)
        return output_path

    def _extract_enabled_entities(self, data: Any) -> List[str]:
        if not isinstance(data, dict):
            return list(self.ENTITY_TYPES)

        raw_entities: Optional[List[Any]] = None
        if "enabled_entities" in data:
            raw = data.get("enabled_entities")
            raw_entities = raw if isinstance(raw, list) else None
        elif "entities" in data:
            raw = data.get("entities")
            raw_entities = raw if isinstance(raw, list) else None
        elif isinstance(data.get("detect"), dict):
            detect_section = data.get("detect", {})
            raw = detect_section.get("enabled_entities")
            if isinstance(raw, list):
                raw_entities = raw
            else:
                raw = detect_section.get("entities")
                raw_entities = raw if isinstance(raw, list) else None

        if raw_entities is None:
            return list(self.ENTITY_TYPES)
        normalized = self._normalize_entities(raw_entities)
        if normalized:
            return normalized
        if len(raw_entities) == 0:
            return []
        return list(self.ENTITY_TYPES)

    def _normalize_entities(self, entities: List[Any]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for raw in entities:
            name = self._normalize_entity_name(raw)
            if name not in self.ENTITY_TYPES:
                continue
            if name in seen:
                continue
            seen.add(name)
            normalized.append(name)
        return normalized

    def load_custom_patterns(self) -> Tuple[List[Tuple[str, str]], List[str]]:
        """追加検出(add_entity)と除外(ommit_entity)を読み込む"""
        self.ensure_config_file()
        try:
            data = self._load_json(self.config_path)
        except Exception as exc:
            logger.warning(f"config.json の読み込みに失敗: {self.config_path} ({exc})")
            return [], []

        add_patterns: List[Tuple[str, str]] = []
        seen_add = set()

        raw_add = data.get("add_entity", {})
        if isinstance(raw_add, dict):
            for raw_entity, raw_patterns in raw_add.items():
                entity = self._normalize_add_entity_key(raw_entity)
                if not entity:
                    continue
                for pattern in self._normalize_pattern_list(raw_patterns):
                    key = (entity, pattern)
                    if key in seen_add:
                        continue
                    seen_add.add(key)
                    add_patterns.append(key)

        raw_ommit = data.get("ommit_entity")
        if raw_ommit is None:
            raw_ommit = data.get("omit_entity", [])
        omit_patterns = self._normalize_pattern_list(raw_ommit)

        return add_patterns, omit_patterns

    @classmethod
    def _normalize_entity_name(cls, value: Any) -> str:
        name = str(value or "").strip().upper()
        return cls.ENTITY_ALIASES.get(name, name)

    @classmethod
    def _normalize_add_entity_key(cls, value: Any) -> str:
        """add_entityキーを正規化（既知キーは従来通り、未知キーはそのまま保持）"""
        raw_name = str(value or "").strip()
        if not raw_name:
            return ""
        normalized_name = cls._normalize_entity_name(raw_name)
        if normalized_name in cls.ENTITY_TYPES:
            return normalized_name
        return raw_name

    @staticmethod
    def _normalize_pattern_list(raw_patterns: Any) -> List[str]:
        if isinstance(raw_patterns, str):
            values = [raw_patterns]
        elif isinstance(raw_patterns, list):
            values = raw_patterns
        else:
            return []

        result: List[str] = []
        seen = set()
        for raw in values:
            pattern = str(raw or "").strip()
            if not pattern or pattern in seen:
                continue
            seen.add(pattern)
            result.append(pattern)
        return result

    @staticmethod
    def _merge_pattern_list(existing: List[str], additional: List[str]) -> List[str]:
        merged: List[str] = []
        seen = set()
        for pattern in list(existing) + list(additional):
            if not pattern or pattern in seen:
                continue
            seen.add(pattern)
            merged.append(pattern)
        return merged

    def _extract_duplicate_settings(self, data: Any) -> Dict[str, str]:
        if not isinstance(data, dict):
            return dict(self.DEFAULT_DUPLICATE_SETTINGS)

        duplicate_section = data.get("duplicate_settings", {})
        if not isinstance(duplicate_section, dict):
            duplicate_section = {}

        raw_entity_overlap_mode = duplicate_section.get(
            "entity_overlap_mode",
            self.DEFAULT_DUPLICATE_SETTINGS["entity_overlap_mode"],
        )
        entity_overlap_mode = str(raw_entity_overlap_mode or "").strip().lower()
        if entity_overlap_mode not in self.DUPLICATE_ENTITY_OVERLAP_MODES:
            entity_overlap_mode = self.DEFAULT_DUPLICATE_SETTINGS["entity_overlap_mode"]

        raw_overlap = duplicate_section.get(
            "overlap",
            self.DEFAULT_DUPLICATE_SETTINGS["overlap"],
        )
        overlap = str(raw_overlap or "").strip().lower()
        if overlap not in self.DUPLICATE_OVERLAP_MODES:
            overlap = self.DEFAULT_DUPLICATE_SETTINGS["overlap"]

        return {
            "entity_overlap_mode": entity_overlap_mode,
            "overlap": overlap,
        }

    @classmethod
    def _default_json_config(cls) -> Dict[str, Any]:
        return {
            "spacy_model": cls.DEFAULT_SPACY_MODEL,
            "enabled_entities": list(cls.ENTITY_TYPES),
            "add_entity": {entity: [] for entity in cls.ENTITY_TYPES},
            "ommit_entity": [],
            "duplicate_settings": dict(cls.DEFAULT_DUPLICATE_SETTINGS),
        }

    def _normalize_config_data(self, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            data = {}
        normalized = dict(data)

        raw_model = normalized.get("spacy_model", self.DEFAULT_SPACY_MODEL)
        if isinstance(raw_model, str) and raw_model.strip():
            normalized["spacy_model"] = raw_model.strip()
        else:
            normalized["spacy_model"] = self.DEFAULT_SPACY_MODEL

        normalized["enabled_entities"] = self._extract_enabled_entities(normalized)

        raw_add = normalized.get("add_entity", {})
        add_entity = {entity: [] for entity in self.ENTITY_TYPES}
        if isinstance(raw_add, dict):
            for raw_entity, raw_patterns in raw_add.items():
                entity = self._normalize_add_entity_key(raw_entity)
                if not entity:
                    continue
                normalized_patterns = self._normalize_pattern_list(raw_patterns)
                current_patterns = add_entity.get(entity, [])
                add_entity[entity] = self._merge_pattern_list(
                    current_patterns,
                    normalized_patterns,
                )
        normalized["add_entity"] = add_entity

        raw_ommit = normalized.get("ommit_entity")
        if raw_ommit is None:
            raw_ommit = normalized.get("omit_entity", [])
        normalized["ommit_entity"] = self._normalize_pattern_list(raw_ommit)
        normalized.pop("omit_entity", None)

        normalized["duplicate_settings"] = self._extract_duplicate_settings(normalized)

        return normalized

    @staticmethod
    def _load_json(path: Path) -> Any:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(text or "{}")

    def _write_json(self, data: Dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        self.config_path.write_text(text, encoding="utf-8")
