#!/usr/bin/env python3
"""
PDF to Image Converter
Converts PDF pages to images for further processing
"""

import fitz  # PyMuPDF
import os
import sys
from pathlib import Path
import argparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def pdf_to_images(pdf_path: str, output_dir: str = "images", dpi: int = 150) -> list:
    """
    Convert PDF pages to images
    
    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to save images
        dpi: Resolution for image conversion
        
    Returns:
        List of created image file paths
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Open PDF
    doc = fitz.open(pdf_path)
    pdf_name = Path(pdf_path).stem
    
    image_paths = []
    
    try:
        for page_num in range(len(doc)):
            # Get page
            page = doc.load_page(page_num)
            
            # Create transformation matrix for DPI
            mat = fitz.Matrix(dpi/72, dpi/72)
            
            # Render page to image
            pix = page.get_pixmap(matrix=mat)
            
            # Save image
            image_path = os.path.join(output_dir, f"{pdf_name}_page_{page_num + 1}.png")
            pix.save(image_path)
            image_paths.append(image_path)
            
            logger.info(f"Converted page {page_num + 1} to {image_path}")
    
    finally:
        doc.close()
    
    return image_paths

def main():
    parser = argparse.ArgumentParser(description="Convert PDF to images")
    parser.add_argument('pdf_path', help='Path to PDF file')
    parser.add_argument('--output', default='images', help='Output directory')
    parser.add_argument('--dpi', type=int, default=150, help='Image resolution (DPI)')
    
    args = parser.parse_args()
    
    try:
        image_paths = pdf_to_images(args.pdf_path, args.output, args.dpi)
        logger.info(f"Successfully converted {len(image_paths)} pages")
        return image_paths
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        return []

if __name__ == "__main__":
    main()