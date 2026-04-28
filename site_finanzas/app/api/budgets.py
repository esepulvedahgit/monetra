from flask import request, jsonify
from app import db
from app.models import Budget
from app.api import api_v1
from app.api.decorators import api_login_required, get_current_api_user
from app.services import finance as svc
from app.services.finance import _budget_dict


@api_v1.get("/budgets")
@api_login_required
def list_budgets():
    user = get_current_api_user()
    return jsonify(svc.get_budgets(user.id, year=request.args.get("year", type=int))), 200


@api_v1.post("/budgets")
@api_login_required
def upsert_budget():
    user = get_current_api_user()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Se requiere JSON"}), 400

    year = data.get("year")
    month = data.get("month")
    amount = data.get("amount")

    if not year or not month:
        return jsonify({"error": "year y month son requeridos"}), 400
    if not (2000 <= int(year) <= 2100):
        return jsonify({"error": "Año inválido"}), 400
    if not (1 <= int(month) <= 12):
        return jsonify({"error": "Mes inválido (1-12)"}), 400

    try:
        amount = float(amount)
        if amount < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Monto inválido"}), 400

    budget = Budget.query.filter_by(
        user_id=user.id, year=int(year), month=int(month)
    ).first()

    if budget:
        budget.amount = amount
        status = 200
    else:
        budget = Budget(user_id=user.id, year=int(year), month=int(month), amount=amount)
        db.session.add(budget)
        status = 201

    db.session.commit()
    return jsonify(_budget_dict(budget)), status


@api_v1.put("/budgets/<int:budget_id>")
@api_login_required
def update_budget(budget_id):
    user = get_current_api_user()
    budget = Budget.query.filter_by(id=budget_id, user_id=user.id).first()
    if not budget:
        return jsonify({"error": "Presupuesto no encontrado"}), 404

    data = request.get_json(silent=True) or {}
    if "amount" in data:
        try:
            amount = float(data["amount"])
            if amount < 0:
                raise ValueError
            budget.amount = amount
        except (TypeError, ValueError):
            return jsonify({"error": "Monto inválido"}), 400

    db.session.commit()
    return jsonify(_budget_dict(budget)), 200
