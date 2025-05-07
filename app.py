from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
import os
import cv2
import numpy as np
import sqlite3
from pathlib import Path
from io import BytesIO
from photo_cascade import (
    load_reference_image,
    get_product_images,
    preprocess_images,
    create_photo_cascade,
    get_average_aspect_ratio,
    calculate_optimal_grid_size
)
import json
from config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Ensure images directory exists
    os.makedirs(app.config['IMAGES_DIR'], exist_ok=True)
    
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    
    def load_image_from_bytes(file_bytes):
        """Load an image from bytes using OpenCV"""
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")
        return img
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/books')
    def books():
        # Get page number from query parameter, default to 1
        page = request.args.get('page', 1, type=int)
        per_page = 15
        
        # Get sort parameters
        sort_by = request.args.get('sort', 'date')  # Default to date
        sort_order = request.args.get('order', 'desc')  # Default to descending
        
        # Check if we're in default state
        is_default_state = sort_by == 'date' and sort_order == 'desc'
        
        valid_sorts = {
            'name': 'title',
            'price': 'price'
        }
        sort_column = valid_sorts.get(sort_by, 'title')
        
        # Connect to database
        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        # Get total count of books
        cursor.execute('SELECT COUNT(*) FROM products WHERE local_image_path IS NOT NULL')
        total_books = cursor.fetchone()[0]
        
        # Calculate total pages
        total_pages = (total_books + per_page - 1) // per_page
        
        # Get paginated products with sorting
        offset = (page - 1) * per_page
        cursor.execute(f'''
        SELECT p.id, p.title, p.price, p.vendor, p.local_image_path, p.url, p.labels
        FROM products p
        WHERE p.local_image_path IS NOT NULL
        ORDER BY {sort_column} {sort_order.upper()}
        LIMIT ? OFFSET ?
        ''', (per_page, offset))
        
        books = []
        for row in cursor.fetchall():
            product_id, title, price, vendor, main_image, url, labels_json = row
            
            # Convert path to URL
            main_image_url = f'/public/{os.path.basename(main_image)}' if main_image else None
            
            # Ensure URL is absolute
            if url and not url.startswith('http'):
                url = f'https://mphonline.com{url}'
            
            # Parse labels from JSON
            labels = json.loads(labels_json) if labels_json else []
            
            books.append({
                'id': product_id,
                'title': title,
                'price': price,
                'vendor': vendor,
                'main_image': main_image_url,
                'url': url,
                'labels': labels
            })
        
        conn.close()
        return render_template('books.html', 
                             books=books, 
                             current_page=page,
                             total_pages=total_pages,
                             current_sort=sort_by,
                             current_order=sort_order,
                             is_default_state=is_default_state)
    
    @app.route('/public/<filename>')
    def serve_image(filename):
        return send_from_directory(app.config['IMAGES_DIR'], filename)
    
    @app.route('/api/create-cascade', methods=['POST'])
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
            original_filename = request.form.get('original_filename', 'photo')
            
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
                image_paths = get_product_images(app.config['DATABASE_PATH'])
                
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
                    output_img,  # Pass the output array directly
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
                    download_name=f'{original_filename}_cascade.jpg'
                )
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    app.run(host=app.config['HOST'], port=app.config['PORT'], debug=app.config['DEBUG']) 