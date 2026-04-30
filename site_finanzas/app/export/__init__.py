from flask import Blueprint

export_bp = Blueprint("export", __name__)

from app.export import route  # noqa: F401, E402
