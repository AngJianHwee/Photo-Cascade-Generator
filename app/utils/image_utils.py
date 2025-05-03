import cv2
import numpy as np
from pathlib import Path
from flask import current_app

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def load_image_from_bytes(file_bytes):
    """Load an image from bytes using OpenCV"""
    nparr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image")
    return img

def save_image(image, filename):
    """Save an image to the images directory"""
    path = Path(current_app.config['IMAGES_DIR']) / filename
    cv2.imwrite(str(path), image)
    return path 