from flask import jsonify

from app.api.decorators import api_login_required, get_current_api_user
from app.api.usd import usd_api
from app.api.usd.schemas import usd_category_schema
from app.models import UsdCategory


@usd_api.get('/categories')
@api_login_required
def list_usd_categories():
    user = get_current_api_user()
    categories = (UsdCategory.query
                  .filter_by(user_id=user.id)
                  .order_by(UsdCategory.name)
                  .all())
    return jsonify([usd_category_schema(category) for category in categories]), 200
