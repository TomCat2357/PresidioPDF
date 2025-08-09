#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - Webアプリケーションルート定義
"""

from flask import (
    render_template,
    request,
    jsonify,
    send_file,
    session,
    redirect,
    url_for,
)
from werkzeug.utils import secure_filename
import os
import json
import uuid
import logging
import traceback
import fitz  # PyMuPDF

from web.web_config import app, logger
from web.web_utils import allowed_file, get_session_app


# Flask ルート定義
@app.route("/")
def index():
    """メインページ"""
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """PDFファイルアップロード"""
    try:
        if "pdf_file" not in request.files:
            return jsonify(
                {"success": False, "message": "ファイルが選択されていません"}
            )

        file = request.files["pdf_file"]
        if file.filename == "":
            return jsonify(
                {"success": False, "message": "ファイルが選択されていません"}
            )

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
            file.save(file_path)

            app_instance = get_session_app()
            result = app_instance.load_pdf_file(file_path)

            if result["success"]:
                return jsonify(result)
            else:
                try:
                    os.remove(file_path)
                except OSError as e:
                    logger.warning(f"アップロード失敗後のファイル削除エラー: {e}")
                return jsonify(result)
        else:
            return jsonify(
                {"success": False, "message": "有効なPDFファイルを選択してください"}
            )

    except Exception as e:
        logger.error(f"ファイルアップロードエラー: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"アップロードエラー: {str(e)}"})


@app.route("/api/detect", methods=["POST"])
def detect_entities():
    """個人情報検出"""
    try:
        logger.info("=== 検出処理開始 ===")
        app_instance = get_session_app()
        logger.info(f"セッションアプリ取得完了: {id(app_instance)}")

        if not app_instance.current_pdf_path:
            logger.error("PDFファイルが読み込まれていません")
            return jsonify(
                {"success": False, "message": "PDFファイルが読み込まれていません"}
            )

        logger.info(f"現在のPDFパス: {app_instance.current_pdf_path}")
        logger.info(f"プロセッサー存在確認: {app_instance.processor is not None}")

        # クライアントから送信された設定 + 手動エンティティを適用
        settings_data = request.get_json() or {}
        logger.info(f"受信した設定データ: {settings_data}")

        if settings_data:
            app_instance.settings.update(settings_data)

            # spaCyモデルが変更された場合は、プロセッサを再初期化
            if "spacy_model" in settings_data:
                spacy_model = settings_data["spacy_model"]
                logger.info(f"spaCyモデルを変更: {spacy_model}")
                app_instance._reinitialize_processor_with_model(spacy_model)

            logger.info(f"セッションの設定を更新: {app_instance.settings}")

        # 手動エンティティを検出前にサーバへ同期して温存
        manual_entities = settings_data.get("manual_entities", [])
        if manual_entities:
            preserved = [e for e in manual_entities if e.get("manual")]
            app_instance.detection_results = preserved

        logger.info("現在の検出対象エンティティ:")
        logger.info(
            f"  - app_instance.settings['entities']: {app_instance.settings.get('entities', [])}"
        )
        if app_instance.processor:
            logger.info(
                f"  - processor enabled entities: {app_instance.processor.config_manager.get_enabled_entities()}"
            )

        logger.info("検出処理実行開始...")
        result = app_instance.run_detection()
        logger.info(f"検出処理完了: success={result.get('success')}")

        if result.get("success"):
            entities_count = len(result.get("entities", []))
            logger.info(f"検出されたエンティティ数: {entities_count}")
        else:
            logger.error(f"検出処理失敗: {result.get('message')}")

        logger.info("=== 検出処理終了 ===")
        return jsonify(result)

    except Exception as e:
        logger.error(f"検出処理エラー: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"検出エラー: {str(e)}"})


@app.route("/api/delete_entity/<int:index>", methods=["DELETE"])
def delete_entity(index):
    """エンティティ削除"""
    try:
        app_instance = get_session_app()
        result = app_instance.delete_entity(index)
        return jsonify(result)
    except Exception as e:
        logger.error(f"エンティティ削除エラー: {e}")
        return jsonify({"success": False, "message": f"削除エラー: {str(e)}"})


@app.route("/api/generate_pdf", methods=["POST"])
def generate_pdf():
    """アノテーション付きPDFを生成（クライアント設定も反映）"""
    try:
        app_instance = get_session_app()
        payload = request.get_json() or {}

        # 1) エンティティ（手動含む）
        if "entities" in payload:
            app_instance.detection_results = payload["entities"]

        # 2) 設定（masking_method / masking_text_mode など）
        settings = payload.get("settings") or {}
        if settings:
            app_instance.settings.update({
                k: v for k, v in settings.items()
                if k in ("masking_method", "masking_text_mode", "entities", "spacy_model")
            })

        result = app_instance.generate_pdf_with_annotations(app.config["UPLOAD_FOLDER"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/download_pdf/<path:filename>")
def download_pdf(filename):
    """生成されたPDFをダウンロード"""
    try:
        logger.info(f"PDFダウンロード要求: {filename}")

        upload_folder = os.path.abspath(app.config["UPLOAD_FOLDER"])
        file_path = os.path.join(upload_folder, filename)
        file_path_abs = os.path.abspath(file_path)

        if not file_path_abs.startswith(upload_folder):
            logger.error(f"セキュリティエラー: 許可されていないパス - {file_path_abs}")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "ファイルアクセスが許可されていません",
                    }
                ),
                403,
            )

        if not os.path.exists(file_path_abs):
            logger.error(f"ファイルが見つかりません: {file_path_abs}")
            return (
                jsonify({"success": False, "message": "ファイルが見つかりません"}),
                404,
            )

        if filename.startswith("annotated_"):
            parts = filename.split("_", 2)
            original_name = parts[2] if len(parts) >= 3 else filename
            download_name = f"masked_{os.path.splitext(original_name)[0]}.pdf"
        else:
            download_name = filename

        logger.info(f"PDFダウンロード開始: {filename} as {download_name}")

        return send_file(
            file_path_abs,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )

    except Exception as e:
        logger.error(f"PDFダウンロードエラー: {e}")
        logger.error(traceback.format_exc())
        return (
            jsonify({"success": False, "message": f"ダウンロードエラー: {str(e)}"}),
            500,
        )


@app.route("/api/settings", methods=["GET", "POST"])
def settings():
    """設定の取得・更新"""
    try:
        app_instance = get_session_app()

        if request.method == "GET":
            return jsonify({"success": True, "settings": app_instance.settings})

        elif request.method == "POST":
            data = request.get_json()
            if "entities" in data:
                app_instance.settings["entities"] = data["entities"]
            if "masking_method" in data:
                app_instance.settings["masking_method"] = data["masking_method"]
            if "spacy_model" in data:
                app_instance.settings["spacy_model"] = data["spacy_model"]
                logger.info(f"spaCyモデル設定を更新: {data['spacy_model']}")

            # 重複除去設定の更新
            deduplication_settings = [
                "deduplication_enabled",
                "deduplication_method",
                "deduplication_priority",
                "deduplication_overlap_mode",
            ]
            for setting in deduplication_settings:
                if setting in data:
                    app_instance.settings[setting] = data[setting]
                    logger.info(f"重複除去設定を更新: {setting} = {data[setting]}")

            logger.info(f"設定更新完了: {app_instance.settings}")
            return jsonify(
                {
                    "success": True,
                    "message": "設定を更新しました",
                    "settings": app_instance.settings,
                }
            )

    except Exception as e:
        logger.error(f"設定処理エラー: {e}")
        return jsonify({"success": False, "message": f"設定エラー: {str(e)}"})


@app.route("/api/highlights/add", methods=["POST"])
def add_highlight():
    # 手動エンティティをサーバに保存
    app_instance = get_session_app()
    data = request.get_json() or {}
    # page_num(0-based)と rect_pdf/rect_norm をそのまま保持
    # line_rects も受け取り保持（複数行ハイライト用）
    if 'line_rects' in data and not isinstance(data['line_rects'], list):
        data['line_rects'] = []
    entity = {
        "entity_type": data.get("entity_type", "CUSTOM"),
        "text": data.get("text", ""),
        "page_num": int(data.get("page_num", max(0, int(data.get("page", 1)) - 1))),
        "rect_pdf": data.get("rect_pdf"),
        "rect_norm": data.get("rect_norm"),
        "source": "manual",
        "manual": True,
        "start_page": int(data.get("start_page", int(data.get("page", 1)))),
        "end_page": int(data.get("end_page", int(data.get("page", 1)))),
        "line_rects": data.get("line_rects", [])
    }
    app_instance.detection_results.append(entity)
    return jsonify({"success": True, "entity": entity})
