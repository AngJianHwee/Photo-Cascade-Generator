import os
from pathlib import Path

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change-in-production'
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    
    # Directory settings
    BASE_DIR = Path(__file__).parent
    IMAGES_DIR = BASE_DIR / 'images'
    UPLOAD_DIR = BASE_DIR / 'uploads'
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + str(BASE_DIR / 'mph_images.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    @staticmethod
    def init_app(app):
        # Ensure directories exist
        os.makedirs(Config.IMAGES_DIR, exist_ok=True)
        os.makedirs(Config.UPLOAD_DIR, exist_ok=True) 