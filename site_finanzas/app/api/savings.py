from datetime import date as date_type
from flask import request, jsonify
from app import db
from app.models import SavingsGoal
from app.api import api_v1
from app.api.decorators import api_login_required, get_current_api_user
from app.services import finance as svc
from app.services.finance import _savings_dict


def _parse_date(value):
    try:
        return date_type.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@api_v1.get("/savings")
@api_login_required
def list_savings():
    user = get_current_api_user()
    completed_param = request.args.get("completed", "all")
    completed = (
        True if completed_param == "true"
        else False if completed_param == "false"
        else None
    )
    return jsonify(svc.get_savings(user.id, completed=completed)), 200


@api_v1.post("/savings")
@api_login_required
def create_savings():
    user = get_current_api_user()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Se requiere JSON"}), 400

    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name es requerido"}), 400

    try:
        target_amount = float(data.get("target_amount", 0))
        if target_amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "target_amount inválido"}), 400

    try:
        current_amount = float(data.get("current_amount", 0))
        if current_amount < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "current_amount inválido"}), 400

    target_date = None
    if data.get("target_date"):
        target_date = _parse_date(data["target_date"])
        if not target_date:
            return jsonify({"error": "target_date inválida (use YYYY-MM-DD)"}), 400

    goal = SavingsGoal(
        user_id=user.id,
        name=name,
        target_amount=target_amount,
        current_amount=current_amount,
        target_date=target_date,
        description=data.get("description", ""),
        is_completed=current_amount >= target_amount,
    )
    db.session.add(goal)
    db.session.commit()
    return jsonify(_savings_dict(goal)), 201


@api_v1.put("/savings/<int:goal_id>")
@api_login_required
def update_savings(goal_id):
    user = get_current_api_user()
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=user.id).first()
    if not goal:
        return jsonify({"error": "Meta no encontrada"}), 404

    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = data["name"].strip()
        if not name:
            return jsonify({"error": "name no puede estar vacío"}), 400
        goal.name = name

    if "target_amount" in data:
        try:
            amount = float(data["target_amount"])
            if amount <= 0:
                raise ValueError
            goal.target_amount = amount
        except (TypeError, ValueError):
            return jsonify({"error": "target_amount inválido"}), 400

    if "current_amount" in data:
        try:
            amount = float(data["current_amount"])
            if amount < 0:
                raise ValueError
            goal.current_amount = amount
        except (TypeError, ValueError):
            return jsonify({"error": "current_amount inválido"}), 400

    if "target_date" in data:
        if data["target_date"] is None:
            goal.target_date = None
        else:
            d = _parse_date(data["target_date"])
            if not d:
                return jsonify({"error": "target_date inválida (use YYYY-MM-DD)"}), 400
            goal.target_date = d

    if "description" in data:
        goal.description = data["description"]

    if "is_completed" in data:
        goal.is_completed = bool(data["is_completed"])

    goal.is_completed = goal.current_amount >= goal.target_amount or goal.is_completed
    db.session.commit()
    return jsonify(_savings_dict(goal)), 200


@api_v1.delete("/savings/<int:goal_id>")
@api_login_required
def delete_savings(goal_id):
    user = get_current_api_user()
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=user.id).first()
    if not goal:
        return jsonify({"error": "Meta no encontrada"}), 404

    db.session.delete(goal)
    db.session.commit()
    return jsonify({"message": "Eliminada"}), 200


@api_v1.post("/savings/<int:goal_id>/contribute")
@api_login_required
def contribute_savings(goal_id):
    user = get_current_api_user()
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=user.id).first()
    if not goal:
        return jsonify({"error": "Meta no encontrada"}), 404

    if goal.is_completed:
        return jsonify({"error": "La meta ya está completada"}), 400

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Se requiere JSON"}), 400

    try:
        amount = float(data.get("amount", 0))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Monto inválido"}), 400

    goal.current_amount = min(float(goal.current_amount) + amount, float(goal.target_amount))
    if goal.current_amount >= float(goal.target_amount):
        goal.is_completed = True

    db.session.commit()
    return jsonify(_savings_dict(goal)), 200
