from flask import Blueprint


mobile_releases_bp = Blueprint('mobile_releases', __name__)

from app.mobile_releases import routes  # noqa: F401, E402
