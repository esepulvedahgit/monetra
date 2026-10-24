from flask import Blueprint

cart_bp = Blueprint('cart', __name__, url_prefix='/carrito')

from app.cart import routes  # noqa: F401
