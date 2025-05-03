from flask import Blueprint

bp = Blueprint('cascade', __name__)

from app.cascade import routes 