import os
import yaml
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    設定管理クラス
    優先順位: デフォルト < YAML設定ファイル < コマンドライン引数
    """

    # サポートされているエンティティタイプ
    ENTITY_TYPES = [
        "PERSON",
        "LOCATION",
        "DATE_TIME",
        "PHONE_NUMBER",
        "INDIVIDUAL_NUMBER",
        "YEAR",
        "PROPER_NOUN",
    ]

    def __init__(self, config_file: Optional[str] = None, args: Optional[Dict] = None):
        """
        Args:
            config_file: YAML設定ファイルのパス
            args: コマンドライン引数の辞書
        """
        self.config_file = config_file or "config.yaml"
        self.args = args or {}
        self.config = self._load_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """最小限のデフォルト設定を返す（YAML設定がない場合のフォールバック）"""
        return {
            "enabled_entities": {},
            "colors": {
                "default": {
                    "font_color": 0,
                    "background_color": 16777215,
                    "highlight_index": 0,
                }
            },
            "custom_names": {
                "name_list": [],
                "name_patterns": [],
                "enabled": False,
                "use_with_auto_detection": True,
            },
            "custom_recognizers": {},
            "features": {
                "logging": {
                    "level": "INFO",
                    "log_to_file": False,
                    "log_file_path": "presidio_log.txt",
                },
                "backup": {"create_backup": False, "backup_suffix": "_backup"},
                "reporting": {
                    "generate_report": False,
                    "report_format": "json",
                    "report_file_prefix": "presidio_report",
                    "include_detected_text": False,
                },
                "processing": {
                    "batch_size": 100,
                    "parallel_processing": False,
                    "skip_processed_files": True,
                },
                "file_handling": {
                    "supported_formats": [".pdf"],
                    "output_suffix": "_highlighted",
                    "recursive_search": True,
                    "output_dir": None,
                },
            },
            "nlp": {
                "spacy_model": "ja_core_news_sm",  # デフォルトは小さいモデル
                "fallback_models": ["ja_core_news_sm", "ja_core_news_md"],
                "auto_download": True,
            },
            "deduplication": {
                "enabled": False,  # デフォルトは無効
                "method": "overlap",  # overlap（重複）, exact（完全一致）, contain（包含）
                "overlap_mode": "partial_overlap",  # contain_only（包含のみ）, partial_overlap（一部重なりも含む）
                "priority": "wider_range",  # wider_range（広い範囲優先）, narrower_range（狭い範囲優先）, entity_type（エンティティタイプ優先）
                "entity_priority_order": [
                    "INDIVIDUAL_NUMBER",
                    "PHONE_NUMBER",
                    "PERSON",
                    "LOCATION",
                    "DATE_TIME",
                    "YEAR",
                    "PROPER_NOUN",
                ],  # エンティティタイプ優先時の順序
            },
            "exclusions": {
                "text_exclusions": [],
                "file_exclusions": ["*_backup.*", "*_highlighted.*", "~$*"],
                "entity_exclusions": {},
            },
            "pdf_processing": {
                "masking": {
                    "method": "annotation",  # annotation, highlight, both
                    "text_display_mode": "verbose",  # silent, minimal, verbose
                    "operation_mode": "append",  # clear_all, append, reset_and_append
                    "duplicate_removal": {
                        "remove_identical": True,  # 完全同一の注釈・ハイライトを除去
                        "comparison_tolerance": 0.1,  # 座標比較の許容誤差（ポイント）
                    },
                    "annotation_settings": {
                        "include_text": False,
                        "font_size": 12,
                        "font_family": "Helvetica",
                    },
                },
                "output_suffix": "_masked",
                "backup_enabled": False,
                "backup_suffix": "_backup",
                "supported_formats": [".pdf"],
                "exclusions": {
                    "files": ["*_backup.*", "*_masked.*"],
                    "text_patterns": [],
                },
                "report": {
                    "generate_report": False,
                    "format": "json",  # json, csv
                    "prefix": "pdf_report",
                    "include_detected_text": False,
                },
                "output_dir": None,
                "processing": {
                    "batch_size": 50,
                    "parallel_processing": False,
                    "skip_processed_files": True,
                },
            },
        }

    def _load_yaml_config(self, config_file: str) -> Dict[str, Any]:
        """YAML設定ファイルを読み込む"""
        try:
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    yaml_config = yaml.safe_load(f)
                    logger.info(f"設定ファイルを読み込みました: {config_file}")
                    return yaml_config or {}
            else:
                logger.info(f"設定ファイルが見つかりません: {config_file}")
                return {}
        except Exception as e:
            logger.warning(f"設定ファイルの読み込みでエラーが発生しました: {e}")
            return {}

    def _deep_merge_dict(self, base: Dict, override: Dict) -> Dict:
        """辞書を再帰的にマージする"""
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge_dict(result[key], value)
            else:
                result[key] = value
        return result

    def _safe_get_config(self, key_path: str, default_value: Any = None):
        """安全に設定値を取得するヘルパーメソッド（ドット記法サポート）"""
        try:
            keys = key_path.split(".")
            value = self.config
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default_value
            return value
        except (KeyError, TypeError, AttributeError):
            return default_value

    def _load_config(self) -> Dict[str, Any]:
        """設定を読み込み、優先順位に従ってマージする

        優先順位:
        1. デフォルト設定（最低）
        2. YAML設定ファイル（中）
        3. コマンドライン引数（最高）

        各設定内では「マスク対象追加 < マスク除外対象追加」の優先順位
        """
        # 1. デフォルト設定（最低優先度）
        config = self._get_default_config()

        # 2. YAML設定ファイル
        if self.config_file:
            yaml_config = self._load_yaml_config(self.config_file)
            config = self._deep_merge_dict(config, yaml_config)

        # 3. コマンドライン引数（最高優先度）
        if self.args:
            # コマンドライン引数を設定構造に変換
            cmd_config = self._convert_args_to_config(self.args)
            config = self._deep_merge_dict(config, cmd_config)

        logger.debug(f"最終設定: {json.dumps(config, indent=2, ensure_ascii=False)}")
        return config

    def _convert_args_to_config(self, args: Dict) -> Dict[str, Any]:
        """コマンドライン引数を設定辞書に変換"""
        config = {}

        # entities引数の処理
        if "entities" in args and args["entities"]:
            enabled_entities = {}
            for entity in args["entities"]:
                enabled_entities[entity] = True
            # 指定されていないエンティティは無効化
            for entity in self.ENTITY_TYPES:
                if entity not in enabled_entities:
                    enabled_entities[entity] = False
            config["enabled_entities"] = enabled_entities

        # カスタム人名設定の引数処理
        if "custom_names" in args and args["custom_names"]:
            try:
                if isinstance(args["custom_names"], str):
                    custom_names_dict = json.loads(args["custom_names"])
                else:
                    custom_names_dict = args["custom_names"]

                if isinstance(custom_names_dict, dict):
                    config["custom_names"] = custom_names_dict
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse custom_names JSON: {e}")

        # 除外設定の引数処理
        if "exclusions" in args and args["exclusions"]:
            try:
                if isinstance(args["exclusions"], str):
                    exclusions_dict = json.loads(args["exclusions"])
                else:
                    exclusions_dict = args["exclusions"]

                if isinstance(exclusions_dict, dict):
                    config["exclusions"] = exclusions_dict
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse exclusions JSON: {e}")

        # PDF処理設定の引数処理
        if "pdf_masking_method" in args and args["pdf_masking_method"]:
            config["pdf_processing"] = config.get("pdf_processing", {})
            config["pdf_processing"]["masking"] = config["pdf_processing"].get(
                "masking", {}
            )
            config["pdf_processing"]["masking"]["method"] = args["pdf_masking_method"]

        if "masking_text_mode" in args and args["masking_text_mode"]:
            config["pdf_processing"] = config.get("pdf_processing", {})
            config["pdf_processing"]["masking"] = config["pdf_processing"].get(
                "masking", {}
            )
            config["pdf_processing"]["masking"]["text_display_mode"] = args[
                "masking_text_mode"
            ]

        if "operation_mode" in args and args["operation_mode"]:
            config["pdf_processing"] = config.get("pdf_processing", {})
            config["pdf_processing"]["masking"] = config["pdf_processing"].get(
                "masking", {}
            )
            config["pdf_processing"]["masking"]["operation_mode"] = args[
                "operation_mode"
            ]

        if "pdf_output_suffix" in args and args["pdf_output_suffix"]:
            config["pdf_processing"] = config.get("pdf_processing", {})
            config["pdf_processing"]["output_suffix"] = args["pdf_output_suffix"]

        if "pdf_backup" in args and args["pdf_backup"] is not None:
            config["pdf_processing"] = config.get("pdf_processing", {})
            config["pdf_processing"]["backup_enabled"] = args["pdf_backup"]

        # 読み取りモード設定
        if "read_mode" in args and args["read_mode"] is not None:
            config["pdf_processing"] = config.get("pdf_processing", {})
            config["pdf_processing"]["read_mode"] = args["read_mode"]

        if "read_report" in args and args["read_report"] is not None:
            config["pdf_processing"] = config.get("pdf_processing", {})
            config["pdf_processing"]["read_report"] = args["read_report"]

        # その他の引数
        if "verbose" in args and args["verbose"]:
            config["features"] = {"logging": {"level": "DEBUG"}}

        if "suffix" in args and args["suffix"]:
            config["features"] = config.get("features", {})
            config["features"]["file_handling"] = config["features"].get(
                "file_handling", {}
            )
            config["features"]["file_handling"]["output_suffix"] = args["suffix"]

        if "backup" in args and args["backup"] is not None:
            config["features"] = config.get("features", {})
            config["features"]["backup"] = {"create_backup": args["backup"]}

        if "report" in args and args["report"] is not None:
            config["features"] = config.get("features", {})
            config["features"]["reporting"] = {"generate_report": args["report"]}

        if "batch_size" in args and args["batch_size"] is not None:
            config["features"] = config.get("features", {})
            config["features"]["processing"] = config["features"].get("processing", {})
            config["features"]["processing"]["batch_size"] = args["batch_size"]

        if "recursive" in args and args["recursive"] is not None:
            config["features"] = config.get("features", {})
            config["features"]["file_handling"] = config["features"].get(
                "file_handling", {}
            )
            config["features"]["file_handling"]["recursive_search"] = args["recursive"]

        # spaCyモデル設定
        if "spacy_model" in args and args["spacy_model"]:
            config["nlp"] = config.get("nlp", {})
            config["nlp"]["spacy_model"] = args["spacy_model"]

        # 重複除去設定
        if "deduplication_mode" in args and args["deduplication_mode"]:
            config["deduplication"] = config.get("deduplication", {})
            config["deduplication"]["enabled"] = True  # モード指定で自動的に有効化
            config["deduplication"]["priority"] = args["deduplication_mode"]

        if "deduplication_overlap_mode" in args and args["deduplication_overlap_mode"]:
            config["deduplication"] = config.get("deduplication", {})
            config["deduplication"]["enabled"] = True  # モード指定で自動的に有効化
            config["deduplication"]["overlap_mode"] = args["deduplication_overlap_mode"]

        # 出力ディレクトリ設定
        if "output_dir" in args and args["output_dir"]:
            config["features"] = config.get("features", {})
            config["features"]["file_handling"] = config["features"].get(
                "file_handling", {}
            )
            config["features"]["file_handling"]["output_dir"] = args["output_dir"]

            config["pdf_processing"] = config.get("pdf_processing", {})
            config["pdf_processing"]["output_dir"] = args["output_dir"]

        return config

    def get_enabled_entities(self) -> List[str]:
        """有効なエンティティタイプのリストを返す"""
        enabled_entities = self._safe_get_config("enabled_entities", {})
        if not isinstance(enabled_entities, dict):
            enabled_entities = {}

        return [entity for entity, is_enabled in enabled_entities.items() if is_enabled]

    def get_entity_colors(self, entity_type: str) -> Dict[str, int]:
        """エンティティタイプの色設定を返す"""
        if entity_type in self.config["colors"]:
            return self.config["colors"][entity_type]
        return self.config["colors"]["default"]

    def get_custom_recognizers(self) -> Dict[str, Dict]:
        """カスタム認識器の設定を返す"""
        return {
            k: v
            for k, v in self.config["custom_recognizers"].items()
            if v.get("enabled", False)
        }

    def get_feature_config(self, feature_name: str) -> Dict[str, Any]:
        """機能設定を返す"""
        return self.config["features"].get(feature_name, {})

    def get_exclusions(self) -> Dict[str, List[str]]:
        """除外設定を返す"""
        return self.config["exclusions"]

    def is_entity_enabled(self, entity_type: str) -> bool:
        """エンティティタイプが有効かどうかを返す"""
        return self.config["enabled_entities"].get(entity_type, False)

    def get_output_suffix(self) -> str:
        """出力ファイルのサフィックスを返す"""
        return self._safe_get_config(
            "features.file_handling.output_suffix", "_highlighted"
        )

    def should_create_backup(self) -> bool:
        """バックアップを作成するかどうかを返す"""
        return self._safe_get_config("features.backup.create_backup", False)

    def get_backup_suffix(self) -> str:
        """バックアップファイルのサフィックスを返す"""
        return self._safe_get_config("features.backup.backup_suffix", "_backup")

    def should_generate_report(self) -> bool:
        """レポートを生成するかどうかを返す"""
        return self._safe_get_config("features.reporting.generate_report", False)

    def get_report_config(self) -> Dict[str, Any]:
        """レポート設定を返す"""
        return self.config["features"]["reporting"]

    def get_logging_config(self) -> Dict[str, Any]:
        """ログ設定を返す"""
        return self.config["features"]["logging"]

    def get_supported_formats(self) -> List[str]:
        """サポートされているファイル形式を返す"""
        return self.config["features"]["file_handling"]["supported_formats"]

    def should_search_recursively(self) -> bool:
        """再帰的検索を行うかどうかを返す"""
        return self.config["features"]["file_handling"]["recursive_search"]

    def get_text_exclusions(self) -> List[str]:
        """テキスト除外パターンを返す"""
        return self._safe_get_config("exclusions.text_exclusions", [])

    def get_file_exclusions(self) -> List[str]:
        """ファイル除外パターンを返す"""
        return self._safe_get_config("exclusions.file_exclusions", [])

    def get_entity_exclusions(
        self, entity_type: str = None
    ) -> Union[List[str], Dict[str, List[str]]]:
        """エンティティ除外リストを返す"""
        entity_exclusions = self._safe_get_config("exclusions.entity_exclusions", {})
        if entity_type:
            return entity_exclusions.get(entity_type, [])
        return entity_exclusions

    def is_entity_excluded(self, entity_type: str, text: str) -> bool:
        """指定されたテキストが除外対象かどうかを判定

        優先順位:
        1. 共通除外ワード（text_exclusions）の部分マッチチェック
        2. エンティティ別除外ワード（entity_exclusions）の完全マッチチェック
        """
        text = text.strip()

        # 1. 共通除外ワードの部分マッチチェック（優先度高）
        text_exclusions = self.get_text_exclusions()
        for exclusion in text_exclusions:
            if text in exclusion:
                logger.debug(
                    f"共通除外ワードにより除外: '{text}' が '{exclusion}' に含まれています"
                )
                return True

        # 2. エンティティ別除外ワードの完全マッチチェック
        entity_exclusions = self.get_entity_exclusions(entity_type)
        if text in entity_exclusions:
            logger.debug(f"エンティティ別除外により除外: '{text}' ({entity_type})")
            return True

        return False

    def get_custom_names_config(self) -> Dict[str, Any]:
        """カスタム人名辞書設定を返す"""
        return self._safe_get_config("custom_names", {})

    def is_custom_names_enabled(self) -> bool:
        """カスタム人名辞書が有効かどうかを返す"""
        return self._safe_get_config("custom_names.enabled", False)

    def get_custom_name_list(self) -> List[str]:
        """カスタム人名リストを返す"""
        return self._safe_get_config("custom_names.name_list", [])

    def get_custom_name_patterns(self) -> List[Dict[str, Any]]:
        """カスタム人名パターンを返す"""
        return self._safe_get_config("custom_names.name_patterns", [])

    def should_use_with_auto_detection(self) -> bool:
        """既存の自動認識と併用するかどうかを返す"""
        return self._safe_get_config("custom_names.use_with_auto_detection", True)

    def save_config(self, output_file: str = None):
        """現在の設定をYAMLファイルに保存"""
        output_file = output_file or self.config_file
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    self.config,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    indent=2,
                )
            logger.info(f"設定を保存しました: {output_file}")
        except Exception as e:
            logger.error(f"設定の保存でエラーが発生しました: {e}")
            raise

    def reload_config(self):
        """設定を再読み込み"""
        self.config = self._load_config()
        logger.info("設定を再読み込みしました")

    # PDF処理用の設定メソッド
    def get_pdf_masking_method(self) -> str:
        """PDFマスキング方式を返す"""
        return self._safe_get_config("pdf_processing.masking.method", "annotation")

    def get_pdf_output_suffix(self) -> str:
        """PDF出力ファイルのサフィックスを返す"""
        return self._safe_get_config("pdf_processing.output_suffix", "_masked")

    def is_pdf_backup_enabled(self) -> bool:
        """PDFバックアップが有効かどうかを返す"""
        return self._safe_get_config("pdf_processing.backup_enabled", False)

    def get_pdf_backup_suffix(self) -> str:
        """PDFバックアップファイルのサフィックスを返す"""
        return self._safe_get_config("pdf_processing.backup_suffix", "_backup")

    def get_pdf_supported_formats(self) -> List[str]:
        """PDFサポート形式を返す"""
        return self._safe_get_config("pdf_processing.supported_formats", [".pdf"])

    def get_pdf_annotation_settings(self) -> Dict[str, Any]:
        """PDF注釈設定を返す"""
        return self._safe_get_config(
            "pdf_processing.masking.annotation_settings",
            {"include_text": False, "font_size": 12, "font_family": "Helvetica"},
        )

    def get_masking_text_display_mode(self) -> str:
        """マスキング時の文字表示モードを返す"""
        return self._safe_get_config(
            "pdf_processing.masking.text_display_mode", "verbose"
        )

    def get_operation_mode(self) -> str:
        """注釈・ハイライトの操作モードを返す"""
        return self._safe_get_config("pdf_processing.masking.operation_mode", "append")

    def should_remove_identical_annotations(self) -> bool:
        """完全同一の注釈・ハイライト除去が有効かどうかを返す"""
        return self._safe_get_config(
            "pdf_processing.masking.duplicate_removal.remove_identical", True
        )

    def get_annotation_comparison_tolerance(self) -> float:
        """注釈比較の許容誤差を返す"""
        return self._safe_get_config(
            "pdf_processing.masking.duplicate_removal.comparison_tolerance", 0.1
        )

    def get_pdf_file_exclusions(self) -> List[str]:
        """PDF処理のファイル除外パターンを返す"""
        return self._safe_get_config(
            "pdf_processing.exclusions.files", ["*_backup.*", "*_masked.*"]
        )

    def get_pdf_text_exclusions(self) -> List[str]:
        """PDF処理のテキスト除外パターンを返す"""
        return self._safe_get_config("pdf_processing.exclusions.text_patterns", [])

    def should_generate_pdf_report(self) -> bool:
        """PDFレポートを生成するかどうかを返す"""
        return self._safe_get_config("pdf_processing.report.generate_report", False)

    def get_pdf_report_format(self) -> str:
        """PDFレポート形式を返す"""
        return self._safe_get_config("pdf_processing.report.format", "json")

    def get_pdf_report_prefix(self) -> str:
        """PDFレポートのプレフィックスを返す"""
        return self._safe_get_config("pdf_processing.report.prefix", "pdf_report")

    def should_include_detected_text_in_pdf_report(self) -> bool:
        """PDFレポートに検出テキストを含めるかどうかを返す"""
        return self._safe_get_config(
            "pdf_processing.report.include_detected_text", False
        )

    def get_pdf_batch_size(self) -> int:
        """PDF処理のバッチサイズを返す"""
        return self._safe_get_config("pdf_processing.processing.batch_size", 50)

    def is_pdf_parallel_processing_enabled(self) -> bool:
        """PDF並列処理が有効かどうかを返す"""
        return self._safe_get_config(
            "pdf_processing.processing.parallel_processing", False
        )

    def should_skip_processed_pdf_files(self) -> bool:
        """処理済みPDFファイルをスキップするかどうかを返す"""
        return self._safe_get_config(
            "pdf_processing.processing.skip_processed_files", True
        )

    def is_pdf_file_excluded(self, file_path: str) -> bool:
        """PDFファイルが除外対象かどうかを判定"""
        import fnmatch

        file_exclusions = self.get_pdf_file_exclusions()
        file_name = os.path.basename(file_path)

        for pattern in file_exclusions:
            if fnmatch.fnmatch(file_name, pattern):
                logger.debug(f"PDFファイル除外パターンにマッチ: {file_path}")
                return True

        return False

    def is_read_mode_enabled(self) -> bool:
        """読み取りモードが有効かどうかを返す"""
        return self._safe_get_config("pdf_processing.read_mode", False)

    def should_generate_read_report(self) -> bool:
        """読み取りレポートを生成するかどうかを返す"""
        return self._safe_get_config("pdf_processing.read_report", True)

    # NLP/spaCy設定メソッド
    def get_spacy_model(self) -> str:
        """使用するspaCyモデル名を返す"""
        return self._safe_get_config("nlp.spacy_model", "ja_core_news_sm")

    def set_spacy_model(self, model_name: str):
        """spaCyモデル名を設定する"""
        if "nlp" not in self.config:
            self.config["nlp"] = {}
        self.config["nlp"]["spacy_model"] = model_name
        logger.info(f"spaCyモデル設定を更新: {model_name}")

    def get_fallback_models(self) -> List[str]:
        """フォールバックモデルのリストを返す"""
        return self._safe_get_config(
            "nlp.fallback_models", ["ja_core_news_sm", "ja_core_news_md"]
        )

    def is_auto_download_enabled(self) -> bool:
        """モデル自動ダウンロードが有効かどうかを返す"""
        return self._safe_get_config("nlp.auto_download", True)

    # 重複除去設定メソッド
    def is_deduplication_enabled(self) -> bool:
        """重複除去が有効かどうかを返す"""
        return self._safe_get_config("deduplication.enabled", False)

    def get_deduplication_method(self) -> str:
        """重複除去の方法を返す"""
        return self._safe_get_config("deduplication.method", "overlap")

    def get_deduplication_priority(self) -> str:
        """重複除去の優先順位基準を返す"""
        return self._safe_get_config("deduplication.priority", "wider_range")

    def get_entity_priority_order(self) -> List[str]:
        """エンティティタイプの優先順序を返す"""
        return self._safe_get_config(
            "deduplication.entity_priority_order",
            [
                "INDIVIDUAL_NUMBER",
                "PHONE_NUMBER",
                "PERSON",
                "LOCATION",
                "DATE_TIME",
                "YEAR",
                "PROPER_NOUN",
            ],
        )

    def get_deduplication_overlap_mode(self) -> str:
        """重複の重なり判定モードを返す"""
        return self._safe_get_config("deduplication.overlap_mode", "partial_overlap")

    def get_output_dir(self) -> Optional[str]:
        """出力ディレクトリを返す"""
        # PDF処理用の設定を優先的にチェック
        pdf_output_dir = self._safe_get_config("pdf_processing.output_dir", None)
        if pdf_output_dir:
            return pdf_output_dir

        # 一般的なファイル処理設定をチェック
        return self._safe_get_config("features.file_handling.output_dir", None)
