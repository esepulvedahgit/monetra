from flask import Blueprint

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

from app.api import (  # noqa: F401
    audit,
    auth,
    budgets,
    carts,
    categories,
    dashboard,
    insights,
    recurring,
    savings,
    transactions,
)
from app.api.usd import usd_api

api_v1.register_blueprint(usd_api)
