from flask import Blueprint

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

from app.api import auth, transactions, categories, budgets, dashboard, recurring, savings, audit, insights  # noqa: F401, E402
