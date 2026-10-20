from flask import Blueprint

auth = Blueprint('auth', __name__)

from app.auth import (
    pin_routes,  # noqa: F401
    routes,  # noqa: F401
)
