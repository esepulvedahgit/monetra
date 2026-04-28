from flask import request, jsonify
from app.api import api_v1
from app.api.decorators import api_login_required, get_current_api_user
from app.services import finance as svc


@api_v1.get("/categories")
@api_login_required
def list_categories():
    user = get_current_api_user()
    return jsonify(svc.get_categories(user.id, tx_type=request.args.get("type"))), 200
