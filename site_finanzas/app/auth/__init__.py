from flask import Blueprint

auth = Blueprint('auth', __name__)

from app.auth import routes          # noqa: F401, E402
from app.auth import pin_routes       # noqa: F401, E402
