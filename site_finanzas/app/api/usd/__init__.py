from flask import Blueprint

usd_api = Blueprint('usd_api', __name__, url_prefix='/usd')

from app.api.usd import categories, transactions  # noqa: E402, F401
