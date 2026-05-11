from datetime import date
from flask import request, jsonify
from app import db
from app.models import RecurringTransaction, Category
from app.api import api_v1
from app.api.decorators import api_login_required, get_current_api_user
from app.services import finance as svc
from app.services.finance import _recurring_dict


def _owned_category(user, category_id, tx_type):
    cat = Category.query.filter(
        (Category.id == category_id),
        (Category.user_id == user.id) | (Category.user_id.is_(None)),
    ).first()
    if not cat:
        return None, "Categoría no encontrada"
    if cat.type != tx_type:
        return None, "El tipo de categoría no coincide con el tipo de transacción recurrente"
    return cat, None


@api_v1.get("/recurring")
@api_login_required
def list_recurring():
    user = get_current_api_user()
    return jsonify(
        svc.get_recurring(
            user.id,
            tx_type=request.args.get("type"),
            active_only=request.args.get("active_only", "false").lower() == "true",
        )
    ), 200


@api_v1.post("/recurring")
@api_login_required
def create_recurring():
    user = get_current_api_user()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Se requiere JSON"}), 400

    tx_type = data.get("type")
    if tx_type not in ("income", "expense"):
        return jsonify({"error": "Tipo debe ser 'income' o 'expense'"}), 400

    try:
        amount = float(data.get("amount", 0))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Monto inválido"}), 400

    try:
        day = int(data.get("day_of_month", 1))
        if not (1 <= day <= 28):
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "day_of_month debe ser entre 1 y 28"}), 400

    category_id = data.get("category_id")
    if not category_id:
        return jsonify({"error": "category_id es requerido"}), 400
    cat, err = _owned_category(user, category_id, tx_type)
    if err:
        return jsonify({"error": err}), 400

    rec = RecurringTransaction(
        user_id=user.id,
        type=tx_type,
        amount=amount,
        description=data.get("description", ""),
        category_id=category_id,
        day_of_month=day,
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(rec)
    db.session.commit()
    db.session.refresh(rec)
    return jsonify(_recurring_dict(rec)), 201


@api_v1.put("/recurring/<int:rec_id>")
@api_login_required
def update_recurring(rec_id):
    user = get_current_api_user()
    rec = RecurringTransaction.query.filter_by(id=rec_id, user_id=user.id).first()
    if not rec:
        return jsonify({"error": "Transacción recurrente no encontrada"}), 404

    data = request.get_json(silent=True) or {}

    if "type" in data:
        if data["type"] not in ("income", "expense"):
            return jsonify({"error": "Tipo inválido"}), 400
        rec.type = data["type"]

    if "amount" in data:
        try:
            amount = float(data["amount"])
            if amount <= 0:
                raise ValueError
            rec.amount = amount
        except (TypeError, ValueError):
            return jsonify({"error": "Monto inválido"}), 400

    if "day_of_month" in data:
        try:
            day = int(data["day_of_month"])
            if not (1 <= day <= 28):
                raise ValueError
            rec.day_of_month = day
        except (TypeError, ValueError):
            return jsonify({"error": "day_of_month debe ser entre 1 y 28"}), 400

    if "description" in data:
        rec.description = data["description"]

    if "category_id" in data:
        cat, err = _owned_category(user, data["category_id"], rec.type)
        if err:
            return jsonify({"error": err}), 400
        rec.category_id = data["category_id"]

    if "is_active" in data:
        rec.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify(_recurring_dict(rec)), 200


@api_v1.delete("/recurring/<int:rec_id>")
@api_login_required
def delete_recurring(rec_id):
    return jsonify({
        "error": "Las recurrentes no pueden eliminarse. Usa POST /recurring/<id>/finalize para finalizarla."
    }), 405


@api_v1.post("/recurring/<int:rec_id>/finalize")
@api_login_required
def finalize_recurring(rec_id):
    user = get_current_api_user()
    rec = RecurringTransaction.query.filter_by(id=rec_id, user_id=user.id).first()
    if not rec:
        return jsonify({"error": "Transacción recurrente no encontrada"}), 404
    if not rec.is_active:
        return jsonify({"error": "La recurrente ya está finalizada"}), 409

    rec.end_date = date.today()
    rec.is_active = False
    db.session.commit()
    return jsonify(_recurring_dict(rec)), 200
