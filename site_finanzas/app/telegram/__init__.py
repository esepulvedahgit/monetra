from flask import Blueprint

telegram_bp = Blueprint('telegram', __name__)

from app.telegram import routes  # noqa: F401,E402
