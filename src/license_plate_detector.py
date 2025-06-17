#!/usr/bin/env python3
"""
License Plate Detection using YOLOv5
Implementation of RevYOLOv5 Step 1 - License Plate Detection

This module implements license plate detection using YOLOv5 model.
Based on the RevYOLOv5 guide: https://izutsu.aa0.netvolante.jp/pukiwiki/?RevYOLOv5_3
"""

import os
import sys
import argparse
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Union
import logging
from ultralytics import YOLO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LicensePlateDetector:
    """
    License Plate Detector using YOLOv5
    
    This class implements license plate detection functionality using a pre-trained
    or custom-trained YOLOv5 model for detecting license plate regions in images.
    """
    
    def __init__(self, 
                 model_path: Optional[str] = None,
                 confidence_threshold: float = 0.5,
                 device: str = 'auto'):
        """
        Initialize the License Plate Detector
        
        Args:
            model_path: Path to custom trained model. If None, uses YOLOv5s pre-trained
            confidence_threshold: Minimum confidence for detections
            device: Device to run inference on ('cpu', 'cuda', or 'auto')
        """
        self.confidence_threshold = confidence_threshold
        self.device = device if device != 'auto' else ('0' if self._cuda_available() else 'cpu')
        self.model = self._load_model(model_path)
        
    def _cuda_available(self) -> bool:
        """Check if CUDA is available"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def _load_model(self, model_path: Optional[str]):
        """Load YOLO model using ultralytics"""
        try:
            if model_path and os.path.exists(model_path):
                # Load custom trained model
                logger.info(f"Loading custom model from {model_path}")
                model = YOLO(model_path)
            else:
                # Load pre-trained YOLOv8n model (smaller and faster)
                logger.info("Loading YOLOv8n pre-trained model")
                model = YOLO('yolov8n.pt')
            
            # Set confidence threshold
            model.conf = self.confidence_threshold
            return model
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def detect_license_plates(self, 
                            image_path: Union[str, np.ndarray],
                            save_results: bool = True,
                            output_dir: str = "results") -> List[dict]:
        """
        Detect license plates in an image
        
        Args:
            image_path: Path to image file or numpy array
            save_results: Whether to save annotated results
            output_dir: Directory to save results
            
        Returns:
            List of detection results with bounding boxes and confidence scores
        """
        try:
            # Load image
            if isinstance(image_path, str):
                if not os.path.exists(image_path):
                    raise FileNotFoundError(f"Image file not found: {image_path}")
                img = cv2.imread(image_path)
                img_name = Path(image_path).stem
            else:
                img = image_path
                img_name = "image"
            
            if img is None:
                raise ValueError("Failed to load image")
            
            # Run inference
            results = self.model(img, device=self.device)
            
            # Parse results
            detections = self._parse_results(results, img_name)
            
            # Save results if requested
            if save_results:
                self._save_results(results, img, img_name, output_dir)
            
            return detections
            
        except Exception as e:
            logger.error(f"Detection failed: {e}")
            raise
    
    def _parse_results(self, results, img_name: str) -> List[dict]:
        """Parse YOLO results into structured format"""
        detections = []
        
        # Extract predictions from ultralytics results
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    # Get box coordinates, confidence, and class
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = box.conf[0].cpu().numpy()
                    class_id = int(box.cls[0].cpu().numpy())
                    
                    # Filter for vehicle-related classes that might contain license plates
                    # YOLO classes: car=2, motorcycle=3, bus=5, truck=7
                    vehicle_classes = [2, 3, 5, 7]
                    
                    detection_info = {
                        'image_name': img_name,
                        'bbox': [int(x1), int(y1), int(x2), int(y2)],
                        'confidence': float(conf),
                        'class_id': class_id,
                        'class_name': self.model.names[class_id]
                    }
                    
                    # For now, detect all objects but prioritize vehicles
                    if class_id in vehicle_classes:
                        detection_info['is_vehicle'] = True
                    else:
                        detection_info['is_vehicle'] = False
                    
                    detections.append(detection_info)
                    
                    logger.info(f"Detected {detection_info['class_name']} "
                              f"(conf: {conf:.3f}) at {detection_info['bbox']}")
        
        return detections
    
    def _save_results(self, results, img: np.ndarray, img_name: str, output_dir: str):
        """Save detection results with annotations"""
        try:
            # Create output directory
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Save annotated image using ultralytics results
            for i, result in enumerate(results):
                annotated_img = result.plot()  # Get annotated image
                output_path = os.path.join(output_dir, f"{img_name}_detected.jpg")
                cv2.imwrite(output_path, annotated_img)
                
                logger.info(f"Results saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
    
    def process_folder(self, 
                      folder_path: str, 
                      output_dir: str = "results",
                      image_extensions: List[str] = None) -> List[dict]:
        """
        Process all images in a folder
        
        Args:
            folder_path: Path to folder containing images
            output_dir: Directory to save results
            image_extensions: List of image file extensions to process
            
        Returns:
            List of all detection results
        """
        if image_extensions is None:
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        
        folder_path = Path(folder_path)
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        all_detections = []
        
        # Find all image files
        image_files = []
        for ext in image_extensions:
            image_files.extend(folder_path.glob(f"*{ext}"))
            image_files.extend(folder_path.glob(f"*{ext.upper()}"))
        
        if not image_files:
            logger.warning(f"No image files found in {folder_path}")
            return all_detections
        
        logger.info(f"Processing {len(image_files)} images...")
        
        for img_file in image_files:
            try:
                logger.info(f"Processing {img_file.name}...")
                detections = self.detect_license_plates(
                    str(img_file), 
                    save_results=True, 
                    output_dir=output_dir
                )
                all_detections.extend(detections)
                
            except Exception as e:
                logger.error(f"Failed to process {img_file}: {e}")
                continue
        
        return all_detections


def main():
    """Main function for command line usage"""
    parser = argparse.ArgumentParser(description="License Plate Detection using YOLOv5")
    parser.add_argument('input', help='Input image file or folder path')
    parser.add_argument('--model', help='Path to custom trained model')
    parser.add_argument('--confidence', type=float, default=0.5,
                       help='Confidence threshold (default: 0.5)')
    parser.add_argument('--output', default='results',
                       help='Output directory (default: results)')
    parser.add_argument('--device', default='auto',
                       help='Device to use (cpu/cuda/auto, default: auto)')
    
    args = parser.parse_args()
    
    try:
        # Initialize detector
        detector = LicensePlateDetector(
            model_path=args.model,
            confidence_threshold=args.confidence,
            device=args.device
        )
        
        # Process input
        input_path = Path(args.input)
        
        if input_path.is_file():
            # Single image
            logger.info(f"Processing single image: {input_path}")
            detections = detector.detect_license_plates(
                str(input_path), 
                save_results=True, 
                output_dir=args.output
            )
            
            logger.info(f"Found {len(detections)} detections")
            for detection in detections:
                print(f"  {detection['class_name']}: {detection['confidence']:.3f}")
                
        elif input_path.is_dir():
            # Folder processing
            logger.info(f"Processing folder: {input_path}")
            detections = detector.process_folder(
                str(input_path), 
                output_dir=args.output
            )
            
            logger.info(f"Total detections: {len(detections)}")
            
            # Summary by class
            class_counts = {}
            for detection in detections:
                class_name = detection['class_name']
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
            
            for class_name, count in class_counts.items():
                print(f"  {class_name}: {count}")
        
        else:
            logger.error(f"Invalid input path: {input_path}")
            return 1
            
        return 0
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())