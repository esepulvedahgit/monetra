from datetime import date
from flask import request, jsonify
from app.api import api_v1
from app.api.decorators import api_login_required, get_current_api_user
from app.services import finance as svc


def _parse_period(args):
    today = date.today()
    year = args.get("year", today.year, type=int)
    month = args.get("month", today.month, type=int)
    if not (2000 <= year <= 2100):
        year = today.year
    if not (1 <= month <= 12):
        month = today.month
    return year, month


@api_v1.get("/dashboard/summary")
@api_login_required
def dashboard_summary():
    user = get_current_api_user()
    year, month = _parse_period(request.args)
    return jsonify(svc.get_monthly_summary(user.id, year, month)), 200


@api_v1.get("/dashboard/global")
@api_login_required
def dashboard_global():
    user = get_current_api_user()
    today = date.today()

    year = request.args.get("year", today.year, type=int)
    from_month = max(1, min(12, request.args.get("from_month", 1, type=int)))
    to_month = max(from_month, min(12, request.args.get("to_month", 12, type=int)))

    if not (2000 <= year <= 2100):
        year = today.year

    return jsonify(svc.get_global_summary(user.id, year, from_month, to_month)), 200
