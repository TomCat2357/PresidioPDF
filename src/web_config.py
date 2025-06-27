#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - Webアプリケーション設定
"""

from flask import Flask
import os
import uuid
import logging
import sys
import argparse
from datetime import datetime

# 自プロジェクトのモジュールをインポート
from config_manager import ConfigManager
PRESIDIO_AVAILABLE = False

# Flask アプリケーションの設定
app = Flask(__name__)
app.secret_key = 'presidio-pdf-web-app-secret-key-' + str(uuid.uuid4())

# アップロード設定
UPLOAD_FOLDER = 'web_uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# アップロードフォルダを作成
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ログフォルダを作成
LOG_FOLDER = 'log'
os.makedirs(LOG_FOLDER, exist_ok=True)

# ログ設定
log_filename = os.path.join(LOG_FOLDER, f"presidio_web_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO, # INFOレベルに変更して、本番運用でのログ量を調整
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# グローバル変数（セッション管理）
sessions = {}

# コマンドライン引数の解析
def parse_arguments():
    parser = argparse.ArgumentParser(description='PDF個人情報マスキングツール - Webアプリケーション版')
    parser.add_argument('--gpu', action='store_true', help='GPU（NVIDIA CUDA）を使用する（デフォルト: CPU使用）')
    parser.add_argument('--host', default='0.0.0.0', help='サーバーのホストアドレス（デフォルト: 0.0.0.0）')
    parser.add_argument('--port', type=int, default=5000, help='サーバーのポート番号（デフォルト: 5000）')
    parser.add_argument('--debug', action='store_true', help='デバッグモードで実行')
    return parser.parse_args()

# CPUモードの強制設定
def force_cpu_mode():
    """NVIDIA関連の環境変数を無効化してCPUモードを強制"""
    # CUDA関連の環境変数を無効化
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['NVIDIA_VISIBLE_DEVICES'] = ''
    
    # PyTorch関連
    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = ''
    
    # spaCy関連
    os.environ['SPACY_PREFER_GPU'] = '0'
    
    # Transformers関連
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_DATASETS_OFFLINE'] = '1'
    
    logger.info("CPUモードが強制的に有効化されました。GPU関連機能は無効です。")