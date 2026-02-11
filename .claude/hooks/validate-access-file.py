#!/usr/bin/env python
import json
import os
import sys
from pathlib import Path, PurePath
import platform


def normalize_path_for_comparison(path_str: str) -> str:
    """
    Windows/WSL両対応のパス正規化

    Args:
        path_str: 正規化対象のパス文字列

    Returns:
        正規化されたパス文字列
    """
    try:
        # Pathオブジェクトに変換
        path = Path(path_str)

        # Windowsの場合は大文字小文字を統一（小文字に変換）
        if platform.system() == "Windows":
            # resolve()を使って絶対パスに変換
            resolved_path = path.resolve()
            # 大文字小文字を統一するために文字列として小文字化
            return str(resolved_path).lower().replace("\\", "/")
        else:
            # Linux/WSLの場合はそのまま
            return str(path.resolve()).replace("\\", "/")

    except Exception as e:
        # エラーが発生した場合は元のパスを返す
        return str(path_str).replace("\\", "/")


def is_path_within_directory(file_path: str, directory_path: str) -> bool:
    """
    ファイルパスが指定ディレクトリ内にあるかチェック

    Args:
        file_path: チェック対象のファイルパス
        directory_path: 基準となるディレクトリパス

    Returns:
        ディレクトリ内にある場合True
    """
    try:
        # パスを正規化
        norm_file = normalize_path_for_comparison(file_path)
        norm_dir = normalize_path_for_comparison(directory_path)

        # 末尾のスラッシュを統一
        if not norm_dir.endswith("/"):
            norm_dir += "/"

        # ファイルパスがディレクトリパスで始まるかチェック
        return norm_file.startswith(norm_dir)

    except Exception:
        return False


def validate_file_access(file_path: str, project_root: str) -> tuple[bool, str]:
    """
    ファイルアクセスの妥当性を検証する（Windows/WSL対応版）

    Args:
        file_path: 操作対象のファイルパス
        project_root: プロジェクトルートディレクトリ

    Returns:
        (is_valid, reason): 検証結果とエラー理由
    """

    try:
        # 危険なパターンをチェック
        if ".." in file_path or "~" in file_path:
            return False, f"危険なパス文字列が検出されました: '{file_path}'"

        # 相対パスかどうかをチェック
        path_obj = Path(file_path)

        # 絶対パスの場合、プロジェクトディレクトリ内かチェック
        if path_obj.is_absolute():
            if not is_path_within_directory(file_path, project_root):
                return (
                    False,
                    f"ファイル '{file_path}' はプロジェクトディレクトリ外にあるため、操作が拒否されました。",
                )
        else:
            # 相対パスの場合、プロジェクトルートからの絶対パスを作成してチェック
            abs_file_path = Path(project_root) / file_path
            abs_file_path_str = str(abs_file_path.resolve())

            if not is_path_within_directory(abs_file_path_str, project_root):
                return (
                    False,
                    f"ファイル '{file_path}' はプロジェクトディレクトリ外にあるため、操作が拒否されました。",
                )

        return True, ""

    except Exception as e:
        return False, f"パス検証中にエラーが発生しました: {str(e)}"


def main():
    try:
        # 標準入力からJSONデータを読み込み
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 現在のワーキングディレクトリをプロジェクトルートとして使用
    project_root = os.getcwd()

    # デバッグ情報を出力（必要に応じてコメントアウト）
    # print(f"Debug: Project root: {project_root}", file=sys.stderr)
    # print(f"Debug: Tool name: {tool_name}", file=sys.stderr)
    # print(f"Debug: Platform: {platform.system()}", file=sys.stderr)

    # ファイルパスを取得
    file_path = None

    if tool_name == "Write":
        file_path = tool_input.get("file_path")
    elif tool_name == "Edit":
        file_path = tool_input.get("file_path")
    elif tool_name == "MultiEdit":
        # MultiEditの場合は複数のファイルを確認
        edits = tool_input.get("edits", [])
        for edit in edits:
            edit_path = edit.get("path")
            if edit_path:
                # print(f"Debug: Checking edit path: {edit_path}", file=sys.stderr)
                is_valid, reason = validate_file_access(edit_path, project_root)
                if not is_valid:
                    print(reason, file=sys.stderr)
                    # 出力JSONで操作をブロック
                    print(json.dumps({"decision": "block", "reason": reason}))
                    sys.exit(0)
        # 全てのファイルが有効な場合は通常終了
        sys.exit(0)

    if not file_path:
        # ファイルパスが見つからない場合は許可
        sys.exit(0)

    # print(f"Debug: Checking file path: {file_path}", file=sys.stderr)

    # ファイルアクセスを検証
    is_valid, reason = validate_file_access(file_path, project_root)

    if not is_valid:
        print(reason, file=sys.stderr)
        # 出力JSONで操作をブロック
        print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    # 問題なければ通常通り処理を継続
    sys.exit(0)


if __name__ == "__main__":
    main()
