from flask import Blueprint

usd_bp = Blueprint('usd', __name__, url_prefix='/usd')

from app.usd import routes  # noqa: E402,F401
