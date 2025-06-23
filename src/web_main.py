#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF個人情報マスキングツール - Webアプリケーションメイン実行
"""

import logging
from web_config import app, logger, parse_arguments, force_cpu_mode
from web_utils import set_gpu_mode, get_gpu_mode
import web_routes  # ルート定義をインポート

def main():
    """メイン実行関数"""
    # コマンドライン引数の解析
    args = parse_arguments()
    
    # GPUフラグの設定
    set_gpu_mode(args.gpu)
    
    # CPUモードの強制設定（--gpuが指定されていない場合）
    if not get_gpu_mode():
        force_cpu_mode()
        logger.info("CPUモードで起動します。GPU関連機能は無効化されました。")
    else:
        logger.info("GPUモードで起動します。NVIDIA CUDA機能が有効です。")
    
    logger.info("Webアプリケーション開始")
    logger.info(f"サーバー設定: {args.host}:{args.port}")
    logger.info(f"デバッグモード: {args.debug}")
    logger.info(f"処理モード: {'GPU' if get_gpu_mode() else 'CPU'}")
    
    # Flaskアプリケーションの実行
    app.run(debug=args.debug, host=args.host, port=args.port)

if __name__ == '__main__':
    main()