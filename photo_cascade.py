import cv2
import numpy as np
import os
import sqlite3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time
from config import Config

def load_reference_image(reference_path):
    """Load and resize the reference image"""
    img = cv2.imread(reference_path)
    if img is None:
        raise ValueError(f"Could not load reference image: {reference_path}")
    return img

def get_product_images(db_path=None):
    """Get all product images from the database"""
    if db_path is None:
        db_path = Config.DATABASE_PATH
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT local_image_path FROM products WHERE local_image_path IS NOT NULL
    UNION
    SELECT local_path FROM product_images WHERE local_path IS NOT NULL
    ''')
    
    image_paths = [row[0] for row in cursor.fetchall()]
    conn.close()
    return image_paths

def preprocess_images(image_paths, target_size):
    """Pre-load and resize all product images while maintaining their aspect ratios"""
    processed_images = []
    print("Pre-processing images...")
    
    for img_path in tqdm(image_paths):
        try:
            img = cv2.imread(img_path)
            if img is None:
                continue
                
            # Get original dimensions
            h, w = img.shape[:2]
            target_w, target_h = target_size
            
            # Calculate scaling to fit within target size while maintaining aspect ratio
            scale = min(target_w/w, target_h/h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            # Resize image
            resized = cv2.resize(img, (new_w, new_h))
            
            # Calculate padding to center the image
            pad_x = (target_w - new_w) // 2
            pad_y = (target_h - new_h) // 2
            
            # Create padded version of the image
            padded = np.zeros((target_h, target_w, 3), dtype=np.float32)
            padded[pad_y:pad_y+new_h, pad_x:pad_x+new_w] = resized
            
            # Calculate average color of the resized image
            avg_color = np.mean(resized, axis=(0, 1))
            
            processed_images.append({
                'path': img_path,
                'image': padded,
                'avg_color': avg_color,
                'original_size': (w, h),
                'resized_size': (new_w, new_h),
                'aspect_ratio': w/h  # Store original aspect ratio
            })
        except Exception as e:
            print(f"Error processing image {img_path}: {e}")
            continue
    
    return processed_images

def find_best_match(processed_images, target_color):
    """Find the best matching image for a target color"""
    best_match = None
    best_diff = float('inf')
    
    for img_data in processed_images:
        diff = np.sum(np.abs(target_color - img_data['avg_color']))
        if diff < best_diff:
            best_diff = diff
            best_match = img_data
    
    return best_match

def create_blend_mask(size, overlap):
    """Create a smooth blending mask for overlapping cells"""
    mask = np.ones(size, dtype=np.float32)
    blend_width = int(size[0] * overlap)
    
    # Create horizontal blend
    for i in range(blend_width):
        alpha = i / blend_width
        mask[i, :] *= alpha
        mask[-(i+1), :] *= alpha
    
    # Create vertical blend
    for j in range(blend_width):
        alpha = j / blend_width
        mask[:, j] *= alpha
        mask[:, -(j+1)] *= alpha
    
    return mask

def process_cell(args):
    """Process a single cell in parallel"""
    i, j, cell_w, cell_h, ref_cell, processed_images, overlap = args
    avg_color = np.mean(ref_cell, axis=(0, 1))
    best_match = find_best_match(processed_images, avg_color)
    
    if best_match is not None:
        # Get the resized image with its original aspect ratio
        resized = best_match['image']
        
        # Resize to exact cell dimensions
        resized = cv2.resize(resized, (cell_w, cell_h))
        
        # Create blend mask for the cell
        mask = create_blend_mask((cell_h, cell_w), overlap)
        mask = np.dstack([mask] * 3)  # Convert to 3 channels
        
        return i, j, resized, mask
    
    return i, j, None, None

def get_average_aspect_ratio(image_paths):
    """Calculate the average aspect ratio of all product images"""
    aspect_ratios = []
    for img_path in image_paths:
        try:
            img = cv2.imread(img_path)
            if img is None:
                continue
            h, w = img.shape[:2]
            aspect_ratios.append(w/h)
        except Exception as e:
            print(f"Error reading image {img_path}: {e}")
            continue
    
    if not aspect_ratios:
        return 1.0  # Default to square if no valid images
    
    return sum(aspect_ratios) / len(aspect_ratios)

def create_photo_cascade(reference_img, processed_images, output_img, horizontal_grid_size=20, vertical_grid_size=None, overlap=0.2):
    """Create a photo cascade effect using parallel processing with overlapping cells"""
    # Get reference image dimensions
    ref_h, ref_w = reference_img.shape[:2]
    print(f"Reference image dimensions: {ref_w}x{ref_h}")
    print(f"Provided horizontal grid size: {horizontal_grid_size}")
    
    # If vertical grid size is not provided, calculate it based on aspect ratio
    if vertical_grid_size is None:
        aspect_ratio = ref_h / ref_w
        vertical_grid_size = int(round(horizontal_grid_size * aspect_ratio))
    
    print(f"Final grid dimensions: {horizontal_grid_size}x{vertical_grid_size}")
    
    # Calculate consistent cell dimensions
    cell_w = ref_w // horizontal_grid_size
    cell_h = ref_h // vertical_grid_size
    
    # Calculate remaining pixels to distribute
    remaining_w = ref_w - (cell_w * horizontal_grid_size)
    remaining_h = ref_h - (cell_h * vertical_grid_size)
    
    # Create weight sum array for blending
    weight_sum = np.zeros_like(reference_img, dtype=np.float32)
    
    # Prepare arguments for parallel processing
    cell_args = []
    for i in range(horizontal_grid_size):
        for j in range(vertical_grid_size):
            # Calculate cell boundaries
            x1 = i * cell_w
            y1 = j * cell_h
            
            # Add extra pixels to the last cells in each dimension
            x2 = x1 + cell_w + (1 if i == horizontal_grid_size - 1 and remaining_w > 0 else 0)
            y2 = y1 + cell_h + (1 if j == vertical_grid_size - 1 and remaining_h > 0 else 0)
            
            # Ensure we don't exceed image boundaries
            x2 = min(x2, ref_w)
            y2 = min(y2, ref_h)
            
            # Calculate actual cell dimensions
            current_cell_w = x2 - x1
            current_cell_h = y2 - y1
            
            ref_cell = reference_img[y1:y2, x1:x2]
            cell_args.append((i, j, current_cell_w, current_cell_h, ref_cell, processed_images, overlap))
    
    # Process cells in parallel
    print("Processing cells...")
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(process_cell, args) for args in cell_args]
        
        for future in tqdm(as_completed(futures), total=len(futures)):
            i, j, best_match, mask = future.result()
            if best_match is not None:
                # Calculate cell position again to ensure consistency
                x1 = i * cell_w
                y1 = j * cell_h
                x2 = x1 + cell_w + (1 if i == horizontal_grid_size - 1 and remaining_w > 0 else 0)
                y2 = y1 + cell_h + (1 if j == vertical_grid_size - 1 and remaining_h > 0 else 0)
                
                # Ensure we don't exceed image boundaries
                x2 = min(x2, ref_w)
                y2 = min(y2, ref_h)
                
                # Convert best_match to float32 for blending
                best_match_float = best_match.astype(np.float32)
                
                # Apply weighted blending
                output_img[y1:y2, x1:x2] = output_img[y1:y2, x1:x2].astype(np.float32) + (best_match_float * mask)
                weight_sum[y1:y2, x1:x2] += mask
    
    # Normalize the output
    output_img = np.divide(output_img, weight_sum, where=weight_sum > 0)
    output_img = np.clip(output_img, 0, 255).astype(np.uint8)
    
    print("Photo cascade created successfully!")

def calculate_optimal_grid_size(ref_w, ref_h, product_aspect_ratio, target_horizontal_cells=40):
    """Calculate optimal grid size based on product images' aspect ratio"""
    # Calculate the ideal vertical cells based on product aspect ratio
    ideal_vertical_cells = int(round(target_horizontal_cells * product_aspect_ratio))
    
    # Calculate cell dimensions
    cell_w = ref_w // target_horizontal_cells
    cell_h = ref_h // ideal_vertical_cells
    
    # Calculate the actual aspect ratio of the cells
    cell_aspect_ratio = cell_w / cell_h
    
    # Adjust grid size to better match product aspect ratio
    if cell_aspect_ratio > product_aspect_ratio:
        # Need more vertical cells
        vertical_cells = ideal_vertical_cells
        horizontal_cells = int(round(vertical_cells / product_aspect_ratio))
    else:
        # Need more horizontal cells
        horizontal_cells = target_horizontal_cells
        vertical_cells = int(round(horizontal_cells * product_aspect_ratio))
    
    return horizontal_cells, vertical_cells

def main():
    # Paths
    reference_path = "001.webp"
    db_path = "mph_images.db"
    output_path = "photo_cascade.jpg"
    
    try:
        start_time = time.time()
        
        # Load reference image
        print("Loading reference image...")
        reference_img = load_reference_image(reference_path)
        
        # Upscale reference image to 1000px width while maintaining aspect ratio
        h, w = reference_img.shape[:2]
        aspect_ratio = h / w
        new_width = 1000
        new_height = int(new_width * aspect_ratio)
        reference_img = cv2.resize(reference_img, (new_width, new_height))
        print(f"Resized reference image to {new_width}x{new_height}")
        
        # Get product images
        print("Loading product images from database...")
        image_paths = get_product_images(db_path)
        print(f"Found {len(image_paths)} product images")
        
        # Calculate average aspect ratio of product images
        avg_product_aspect_ratio = get_average_aspect_ratio(image_paths)
        print(f"Average product image aspect ratio: {avg_product_aspect_ratio:.2f}")
        
        # Calculate optimal grid size
        horizontal_grid_size, vertical_grid_size = calculate_optimal_grid_size(
            new_width, new_height, avg_product_aspect_ratio, target_horizontal_cells=40
        )
        print(f"Optimal grid dimensions: {horizontal_grid_size}x{vertical_grid_size}")
        
        # Calculate cell size based on grid size
        cell_w = new_width // horizontal_grid_size
        cell_h = new_height // vertical_grid_size
        cell_size = (cell_w, cell_h)
        
        # Pre-process images
        processed_images = preprocess_images(image_paths, cell_size)
        
        # Create photo cascade with aspect-ratio-aware grid
        print("Creating photo cascade...")
        create_photo_cascade(reference_img, processed_images, output_path, 
                           horizontal_grid_size=horizontal_grid_size,
                           vertical_grid_size=vertical_grid_size,
                           overlap=0)
        
        end_time = time.time()
        print(f"Total execution time: {end_time - start_time:.2f} seconds")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 