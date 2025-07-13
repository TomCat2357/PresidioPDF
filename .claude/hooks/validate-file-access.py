#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

def validate_file_access(file_path: str, project_root: str) -> tuple[bool, str]:
    """
    ファイルアクセスの妥当性を検証する
    
    Args:
        file_path: 操作対象のファイルパス
        project_root: プロジェクトルートディレクトリ
        
    Returns:
        (is_valid, reason): 検証結果とエラー理由
    """
    
    try:
        # パスを正規化（../や./などを自動的に解決）
        abs_file_path = Path(file_path).resolve()
        abs_project_root = Path(project_root).resolve()
        
        # プロジェクトディレクトリ内かチェック
        try:
            abs_file_path.relative_to(abs_project_root)
        except ValueError:
            return False, f"ファイル '{file_path}' はプロジェクトディレクトリ外にあるため、操作が拒否されました。"
            
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
                is_valid, reason = validate_file_access(edit_path, project_root)
                if not is_valid:
                    print(reason, file=sys.stderr)
                    # 出力JSONで操作をブロック
                    print(json.dumps({
                        "decision": "block",
                        "reason": reason
                    }))
                    sys.exit(0)
        # 全てのファイルが有効な場合は通常終了
        sys.exit(0)
    
    if not file_path:
        # ファイルパスが見つからない場合は許可
        sys.exit(0)
    
    # ファイルアクセスを検証
    is_valid, reason = validate_file_access(file_path, project_root)
    
    if not is_valid:
        print(reason, file=sys.stderr)
        # 出力JSONで操作をブロック
        print(json.dumps({
            "decision": "block",
            "reason": reason
        }))
        sys.exit(0)
    
    # 問題なければ通常通り処理を継続
    sys.exit(0)

if __name__ == "__main__":
    main()