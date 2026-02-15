"""
PresidioPDF PyQt - 検出設定(.config.toml)管理

- 同一フォルダの .config.toml を読み込み
- 未存在時は自動生成
- インポート/エクスポートを提供
"""

from __future__ import annotations

import logging
import shutil
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DetectConfigService:
    """GUI用検出設定の管理サービス"""

    CONFIG_FILE_NAME = ".config.toml"
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

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.config_path = self.base_dir / self.CONFIG_FILE_NAME

    def ensure_config_file(self) -> List[str]:
        """設定ファイルを保証し、有効エンティティ一覧を返す"""
        if not self.config_path.exists():
            self.save_enabled_entities(list(self.ENTITY_TYPES))
        return self.load_enabled_entities()

    def load_enabled_entities(self) -> List[str]:
        """設定ファイルから有効エンティティ一覧を読み込む"""
        if not self.config_path.exists():
            return list(self.ENTITY_TYPES)

        try:
            text = self.config_path.read_text(encoding="utf-8")
            return self._parse_enabled_entities(text)
        except Exception as exc:
            logger.warning(f"設定ファイルの読み込みに失敗: {self.config_path} ({exc})")
            return list(self.ENTITY_TYPES)

    def save_enabled_entities(self, entities: List[str]) -> List[str]:
        """有効エンティティ一覧を設定ファイルへ保存"""
        normalized = self._normalize_entities(entities)
        toml_text = self._render_toml(normalized)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(toml_text, encoding="utf-8")
        return normalized

    def import_from(self, source_path: Path) -> List[str]:
        """外部TOMLを読み込み、同一フォルダの.config.tomlへ反映"""
        text = Path(source_path).read_text(encoding="utf-8")
        entities = self._parse_enabled_entities(text)
        self.save_enabled_entities(entities)
        return entities

    def export_to(self, output_path: Path) -> Path:
        """同一フォルダの.config.tomlを指定先へ出力"""
        if not self.config_path.exists():
            self.save_enabled_entities(list(self.ENTITY_TYPES))

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.config_path, output_path)
        return output_path

    def _parse_enabled_entities(self, toml_text: str) -> List[str]:
        data = tomllib.loads(toml_text or "")
        raw = self._extract_entities(data)
        if raw is None:
            return list(self.ENTITY_TYPES)
        return self._normalize_entities(raw)

    @staticmethod
    def _extract_entities(data: Dict[str, Any]) -> Optional[List[Any]]:
        if not isinstance(data, dict):
            return None

        if "enabled_entities" in data:
            raw = data.get("enabled_entities")
            return raw if isinstance(raw, list) else None
        if "entities" in data:
            raw = data.get("entities")
            return raw if isinstance(raw, list) else None

        detect_section = data.get("detect")
        if isinstance(detect_section, dict):
            raw = detect_section.get("enabled_entities")
            if isinstance(raw, list):
                return raw
            raw = detect_section.get("entities")
            if isinstance(raw, list):
                return raw

        return None

    def _normalize_entities(self, entities: List[Any]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for raw in entities:
            name = str(raw or "").strip().upper()
            if name == "ADDRESS":
                name = "LOCATION"
            if name not in self.ENTITY_TYPES:
                continue
            if name in seen:
                continue
            seen.add(name)
            normalized.append(name)
        return normalized

    @staticmethod
    def _render_toml(entities: List[str]) -> str:
        lines = [
            "# PresidioPDF GUI detect config",
            "enabled_entities = [",
        ]
        for entity in entities:
            lines.append(f'  "{entity}",')
        lines.append("]")
        lines.append("")
        return "\n".join(lines)
