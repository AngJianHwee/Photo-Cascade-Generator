from flask import request, jsonify, send_file, current_app
from io import BytesIO
import cv2
import numpy as np
from app.utils.image_utils import allowed_file, load_image_from_bytes
from photo_cascade import (
    get_product_images,
    preprocess_images,
    create_photo_cascade,
    get_average_aspect_ratio,
    calculate_optimal_grid_size
)

@bp.route('/create-cascade', methods=['POST'])
def create_cascade():
    try:
        # Check if reference image was uploaded
        if 'reference_image' not in request.files:
            return jsonify({'error': 'No reference image provided'}), 400
        
        file = request.files['reference_image']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Read file into memory
        file_bytes = file.read()
        
        # Get parameters from request
        horizontal_grid_size = int(request.form.get('horizontal_grid_size', 40))
        overlap = float(request.form.get('overlap', 0))
        
        try:
            # Load reference image from bytes
            reference_img = load_image_from_bytes(file_bytes)
            
            # Upscale reference image to 1000px width
            h, w = reference_img.shape[:2]
            aspect_ratio = h / w
            new_width = 1000
            new_height = int(new_width * aspect_ratio)
            reference_img = cv2.resize(reference_img, (new_width, new_height))
            
            # Get product images from database
            image_paths = get_product_images(current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
            
            # Calculate average aspect ratio and optimal grid size
            avg_product_aspect_ratio = get_average_aspect_ratio(image_paths)
            horizontal_grid_size, vertical_grid_size = calculate_optimal_grid_size(
                new_width, new_height, avg_product_aspect_ratio, horizontal_grid_size
            )
            
            # Calculate cell size
            cell_w = new_width // horizontal_grid_size
            cell_h = new_height // vertical_grid_size
            cell_size = (cell_w, cell_h)
            
            # Pre-process images
            processed_images = preprocess_images(image_paths, cell_size)
            
            # Create photo cascade in memory
            output_img = np.zeros_like(reference_img, dtype=np.float32)
            create_photo_cascade(
                reference_img, 
                processed_images, 
                output_img,
                horizontal_grid_size=horizontal_grid_size,
                vertical_grid_size=vertical_grid_size,
                overlap=overlap
            )
            
            # Convert the output image to bytes
            output_img_uint8 = output_img.astype(np.uint8)
            _, buffer = cv2.imencode('.jpg', output_img_uint8)
            output_bytes = BytesIO(buffer)
            
            # Return the generated image
            return send_file(
                output_bytes,
                mimetype='image/jpeg',
                as_attachment=True,
                download_name='photo_cascade.jpg'
            )
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500 