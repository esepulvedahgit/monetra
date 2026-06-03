from flask import Blueprint

scanner_bp = Blueprint('scanner', __name__)

from app.scanner import routes  # noqa: E402,F401
