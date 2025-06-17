#!/usr/bin/env python3
"""
YOLOv11 CPU Training Script
CPU専用でのYOLOv11トレーニング
"""

import os
import sys
import argparse
from pathlib import Path
import torch
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser(description='YOLOv11 CPU Training')
    parser.add_argument('--data', type=str, default='dataset.yaml', 
                       help='Dataset YAML file path')
    parser.add_argument('--model', type=str, default='yolov11s.pt',
                       help='Model file (yolov11s.pt, yolov11m.pt, etc.)')
    
    # Training parameters
    parser.add_argument('--epochs', type=int, default=2, 
                       help='Number of epochs')
    parser.add_argument('--batch', type=int, default=4, 
                       help='Batch size (small for CPU)')
    parser.add_argument('--imgsz', type=int, default=320, 
                       help='Image size (smaller for CPU)')
    parser.add_argument('--workers', type=int, default=2, 
                       help='Number of workers')
    parser.add_argument('--project', type=str, default='runs/train',
                       help='Project directory')
    parser.add_argument('--name', type=str, default='yolov11_cpu',
                       help='Experiment name')
    
    args = parser.parse_args()
    
    print("=== YOLOv11 CPU Training ===")
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print("Device: CPU (forced)")
    print(f"Model: {args.model}")
    print(f"Dataset: {args.data}")
    print(f"Epochs: {args.epochs}")
    print(f"Batch size: {args.batch}")
    print(f"Image size: {args.imgsz}")
    print()
    
    # Check if dataset file exists
    if not Path(args.data).exists():
        print(f"Error: Dataset file {args.data} not found!")
        return
    
    try:
        # Load YOLOv11 model
        print(f"Loading YOLO model: {args.model}")
        model = YOLO(args.model)
        
        # Force CPU device
        device = 'cpu'
        print(f"Forcing device to: {device}")
        
        # Model information
        if hasattr(model, 'model') and model.model is not None:
            total_params = sum(p.numel() for p in model.model.parameters())
            print(f"Model parameters: {total_params:,}")
        
        print("\nStarting training...")
        print("-" * 50)
        
        # Train the model
        results = model.train(
            data=args.data,
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            device=device,  # Force CPU
            workers=args.workers,
            project=args.project,
            name=args.name,
            save_period=1,  # Save every epoch for small training
            patience=50,    # Early stopping patience
            save=True,
            plots=True,
            verbose=True,
            amp=False,      # Disable mixed precision for CPU compatibility
            single_cls=False,
            optimizer='AdamW',
            lr0=0.001,      # Lower learning rate for CPU training
            lrf=0.1,
            momentum=0.9,
            weight_decay=0.0005,
            warmup_epochs=1,
            warmup_momentum=0.8,
            warmup_bias_lr=0.1,
            copy_paste=0.0,
            mixup=0.0,
            hsv_h=0.015,
            hsv_s=0.7,
            hsv_v=0.4,
            degrees=0.0,
            translate=0.1,
            scale=0.5,
            shear=0.0,
            perspective=0.0,
            flipud=0.0,
            fliplr=0.5,
            mosaic=1.0,
            close_mosaic=10
        )
        
        print("\n" + "=" * 50)
        print("Training completed successfully!")
        
        # Print final results
        if hasattr(results, 'metrics') and results.metrics:
            print("\n=== Final Results ===")
            for key, value in results.metrics.items():
                print(f"{key}: {value}")
        
        # Check output directory
        output_dir = Path(args.project) / args.name
        if output_dir.exists():
            print(f"\nResults saved to: {output_dir}")
            weights_dir = output_dir / "weights"
            if weights_dir.exists():
                print(f"Model weights: {weights_dir}")
                best_pt = weights_dir / "best.pt"
                last_pt = weights_dir / "last.pt"
                if best_pt.exists():
                    print(f"  - Best model: {best_pt}")
                if last_pt.exists():
                    print(f"  - Last model: {last_pt}")
        
    except Exception as e:
        print(f"Error during training: {e}")
        print("Please check your environment and dependencies.")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\nTraining script completed.")
    return 0

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)