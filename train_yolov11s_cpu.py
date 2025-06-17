#!/usr/bin/env python3
import os
import argparse
from pathlib import Path
from ultralytics import YOLO
import torch

def main():
    parser = argparse.ArgumentParser(description='YOLOv11s Training on CPU')
    parser.add_argument('--data', type=str, default='dataset_nm64.yaml',
                       help='Dataset YAML file path')
    parser.add_argument('--model', type=str, default='yolov11s.pt',
                       help='Model to use (yolov11s.pt)')
    parser.add_argument('--epochs', type=int, default=2,
                       help='Number of epochs')
    parser.add_argument('--batch', type=int, default=8,
                       help='Batch size (smaller for CPU)')
    parser.add_argument('--imgsz', type=int, default=640,
                       help='Image size')
    parser.add_argument('--device', type=str, default='cpu',
                       help='Device to use (cpu)')
    parser.add_argument('--workers', type=int, default=2,
                       help='Number of workers (smaller for CPU)')
    parser.add_argument('--project', type=str, default='runs/train',
                       help='Output directory')
    parser.add_argument('--name', type=str, default='yolov11s_nm64_2ep',
                       help='Experiment name')
    
    args = parser.parse_args()
    
    # CPU環境確認
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"Device: {args.device}")
    
    # データセット設定ファイルの存在確認
    if not os.path.exists(args.data):
        print(f"Error: Dataset file {args.data} not found!")
        return
    
    # YOLOモデルロード
    print(f"Loading YOLO model: {args.model}")
    model = YOLO(args.model)
    
    # モデル情報表示
    print(f"Model: {args.model}")
    print(f"Parameters: {sum(p.numel() for p in model.model.parameters()):,}")
    
    # トレーニング設定
    train_args = {
        'data': args.data,
        'epochs': args.epochs,
        'batch': args.batch,
        'imgsz': args.imgsz,
        'device': args.device,
        'workers': args.workers,
        'project': args.project,
        'name': args.name,
        'save_period': 1,  # 毎エポック保存
        'patience': 10,   # 早期停止設定
        'save': True,
        'plots': True,
        'verbose': True,
        'cache': False,   # CPU環境では無効
        'close_mosaic': 0  # モザイク無効
    }
    
    print("\n=== Training Configuration ===")
    for key, value in train_args.items():
        print(f"{key}: {value}")
    print("="*50)
    
    # トレーニング実行
    print("Starting training...")
    try:
        results = model.train(**train_args)
        print("Training completed successfully!")
        
        # 結果サマリー表示
        if hasattr(results, 'results_dict'):
            print("\n=== Training Summary ===")
            for key, value in results.results_dict.items():
                print(f"{key}: {value}")
        
        # 最終モデルパス表示
        best_model_path = Path(args.project) / args.name / "weights" / "best.pt"
        last_model_path = Path(args.project) / args.name / "weights" / "last.pt"
        
        if best_model_path.exists():
            print(f"\nBest model saved to: {best_model_path}")
        if last_model_path.exists():
            print(f"Last model saved to: {last_model_path}")
            
    except Exception as e:
        print(f"Error during training: {e}")
        raise

if __name__ == '__main__':
    main()