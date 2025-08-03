#!/usr/bin/env python
import json
import sys
import os
import re

# 現在のプロジェクトディレクトリを取得
PROJECT_DIR = os.getcwd()

try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(1)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})
command = tool_input.get("command", "")

if tool_name != "Bash":
    sys.exit(0)

# cdコマンドの検出
cd_match = re.search(r"^\s*cd\s+(.+)", command)
if cd_match:
    target_dir = cd_match.group(1).strip().strip("\"'")

    # 絶対パスに変換
    if not os.path.isabs(target_dir):
        target_dir = os.path.join(PROJECT_DIR, target_dir)

    target_dir = os.path.abspath(target_dir)

    # プロジェクトディレクトリ外かチェック
    if not target_dir.startswith(PROJECT_DIR):
        response = {
            "decision": "block",
            "reason": f"プロジェクトディレクトリ外（{target_dir}）への移動は許可されていません。プロジェクト内（{PROJECT_DIR}）にとどまってください。",
        }
        print(json.dumps(response, ensure_ascii=False))
        sys.exit(0)

# 問題なければ実行を許可
sys.exit(0)
