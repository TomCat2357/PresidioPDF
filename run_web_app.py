#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - Webアプリケーション起動スクリプト
"""

import sys
import os

# srcディレクトリをPythonパスに追加
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

# Webアプリケーションを起動
if __name__ == '__main__':
    from presidio_web_app import app
    app.run(debug=True, host='0.0.0.0', port=5000)