
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.books import bp as books_bp
    app.register_blueprint(books_bp, url_prefix='/books')

    from app.cascade import bp as cascade_bp
    app.register_blueprint(cascade_bp, url_prefix='/api')

    return app 