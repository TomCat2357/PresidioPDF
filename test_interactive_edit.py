#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
インタラクティブPDF編集機能のテストスクリプト
"""

import logging
import sys
import os

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pdf_interactive_gui import PDFInteractiveGUI
import tkinter as tk

def test_interactive_gui():
    """インタラクティブGUIのテスト"""
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('interactive_test.log', encoding='utf-8')
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("インタラクティブPDF編集GUIテストを開始")
    
    try:
        # Tkinterルートウィンドウを作成
        root = tk.Tk()
        
        # アプリケーションを作成して実行
        app = PDFInteractiveGUI(root)
        
        logger.info("GUIアプリケーションを起動")
        app.run()
        
    except Exception as e:
        logger.error(f"テスト実行エラー: {e}")
        raise

if __name__ == "__main__":
    test_interactive_gui()