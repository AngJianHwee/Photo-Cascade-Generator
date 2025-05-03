import os
from dotenv import load_dotenv

# Load environment variables from config.env
load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-key-please-change-in-production')
    ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_DEBUG', '1') == '1'

    # File paths
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'mph_images.db')
    IMAGES_DIR = os.getenv('IMAGES_DIR', 'images')
    UPLOAD_DIR = os.getenv('UPLOAD_DIR', 'uploads')

    # File upload settings
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))  # 16MB in bytes
    ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'png,jpg,jpeg,webp').split(','))

    # Server settings
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))

    # Ensure directories exist
    @staticmethod
    def init_app(app):
        os.makedirs(Config.IMAGES_DIR, exist_ok=True)
        os.makedirs(Config.UPLOAD_DIR, exist_ok=True) 