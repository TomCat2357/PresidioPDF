#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - Webアプリケーションユーティリティ
"""

import uuid
from flask import session
from presidio_web_core import PresidioPDFWebApp

# アップロード許可ファイル形式
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """アップロードされたファイルが許可されているかチェック"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# グローバル変数でGPU使用フラグを管理
_USE_GPU = False

# セッション管理
sessions = {}

def set_gpu_mode(use_gpu: bool):
    """GPU使用モードを設定"""
    global _USE_GPU
    _USE_GPU = use_gpu

def get_gpu_mode() -> bool:
    """現在のGPU使用モードを取得"""
    return _USE_GPU

def get_session_app() -> PresidioPDFWebApp:
    """現在のセッションのアプリケーションインスタンスを取得"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    if session_id not in sessions:
        sessions[session_id] = PresidioPDFWebApp(session_id, use_gpu=_USE_GPU)
    
    return sessions[session_id]