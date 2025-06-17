#!/usr/bin/env python3
import os
import glob

def remap_class_ids():
    """Remap class IDs in label files from sparse to dense format (0-52)"""
    
    # Original class IDs found in the dataset
    original_classes = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 15, 16, 18, 19, 20, 21, 22, 23, 26, 27, 29, 30, 31, 32, 34, 35, 36, 37, 38, 40, 41, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 59, 60, 61, 62, 63]
    
    # Create mapping from original ID to new dense ID
    class_mapping = {}
    for new_id, old_id in enumerate(original_classes):
        class_mapping[old_id] = new_id
    
    print("Class ID mapping:")
    for old_id, new_id in class_mapping.items():
        print(f"  {old_id} -> {new_id}")
    
    # Process both train and val label directories
    label_dirs = [
        'nm_dataset_64/train/labels',
        'nm_dataset_64/val/labels'
    ]
    
    total_files = 0
    total_annotations = 0
    
    for label_dir in label_dirs:
        if not os.path.exists(label_dir):
            print(f"Warning: Directory {label_dir} does not exist")
            continue
            
        label_files = glob.glob(os.path.join(label_dir, '*.txt'))
        print(f"\nProcessing {len(label_files)} files in {label_dir}")
        
        for label_file in label_files:
            # Skip cache files
            if 'labels.cache' in label_file:
                continue
                
            # Read original file
            with open(label_file, 'r') as f:
                lines = f.readlines()
            
            # Process and remap class IDs
            new_lines = []
            for line in lines:
                line = line.strip()
                if line:
                    parts = line.split()
                    old_class_id = int(parts[0])
                    
                    if old_class_id in class_mapping:
                        new_class_id = class_mapping[old_class_id]
                        # Replace class ID and keep rest of the line
                        new_line = f"{new_class_id} {' '.join(parts[1:])}\n"
                        new_lines.append(new_line)
                        total_annotations += 1
                    else:
                        print(f"Warning: Unknown class ID {old_class_id} in {label_file}")
            
            # Write back to file
            with open(label_file, 'w') as f:
                f.writelines(new_lines)
            
            total_files += 1
    
    print(f"\nCompleted: Processed {total_files} files with {total_annotations} annotations")
    print(f"Class IDs remapped from sparse (0-63) to dense (0-52) format")

if __name__ == '__main__':
    remap_class_ids()