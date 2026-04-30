from datetime import date as date_type
from flask import request, jsonify
from app import db
from app.models import Transaction, Category
from app.api import api_v1
from app.api.decorators import api_login_required, get_current_api_user
from app.services import finance as svc
from app.services.finance import _tx_dict


def _parse_date(value):
    try:
        return date_type.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _owned_category(user, category_id, tx_type):
    cat = Category.query.filter(
        (Category.id == category_id),
        (Category.user_id == user.id) | (Category.user_id.is_(None)),
    ).first()
    if not cat:
        return None, "Categoría no encontrada"
    if cat.type != tx_type:
        return None, "El tipo de categoría no coincide con el tipo de transacción"
    return cat, None


@api_v1.get("/transactions")
@api_login_required
def list_transactions():
    user = get_current_api_user()
    txs = svc.get_transactions(
        user.id,
        year=request.args.get("year", type=int),
        month=request.args.get("month", type=int),
        tx_type=request.args.get("type"),
        category_id=request.args.get("category_id", type=int),
    )
    return jsonify({"transactions": txs, "total": len(txs)}), 200


@api_v1.post("/transactions")
@api_login_required
def create_transaction():
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

    tx_date = _parse_date(data.get("date"))
    if not tx_date:
        return jsonify({"error": "Fecha inválida (use YYYY-MM-DD)"}), 400

    category_id = data.get("category_id")
    if category_id:
        cat, err = _owned_category(user, category_id, tx_type)
        if err:
            return jsonify({"error": err}), 400
    else:
        category_id = None

    tx = Transaction(
        user_id=user.id,
        type=tx_type,
        amount=amount,
        description=data.get("description", ""),
        date=tx_date,
        category_id=category_id,
        is_demo=False,
    )
    db.session.add(tx)
    db.session.commit()
    db.session.refresh(tx)
    return jsonify(_tx_dict(tx)), 201


@api_v1.put("/transactions/<int:tx_id>")
@api_login_required
def update_transaction(tx_id):
    user = get_current_api_user()
    tx = Transaction.query.filter_by(id=tx_id, user_id=user.id).first()
    if not tx:
        return jsonify({"error": "Transacción no encontrada"}), 404

    data = request.get_json(silent=True) or {}

    if "type" in data:
        if data["type"] not in ("income", "expense"):
            return jsonify({"error": "Tipo inválido"}), 400
        tx.type = data["type"]

    if "amount" in data:
        try:
            amount = float(data["amount"])
            if amount <= 0:
                raise ValueError
            tx.amount = amount
        except (TypeError, ValueError):
            return jsonify({"error": "Monto inválido"}), 400

    if "date" in data:
        d = _parse_date(data["date"])
        if not d:
            return jsonify({"error": "Fecha inválida (use YYYY-MM-DD)"}), 400
        tx.date = d

    if "description" in data:
        tx.description = data["description"]

    if "category_id" in data:
        if data["category_id"] is None:
            tx.category_id = None
        else:
            cat, err = _owned_category(user, data["category_id"], tx.type)
            if err:
                return jsonify({"error": err}), 400
            tx.category_id = data["category_id"]

    db.session.commit()
    return jsonify(_tx_dict(tx)), 200


@api_v1.delete("/transactions/<int:tx_id>")
@api_login_required
def delete_transaction(tx_id):
    user = get_current_api_user()
    tx = Transaction.query.filter_by(id=tx_id, user_id=user.id).first()
    if not tx:
        return jsonify({"error": "Transacción no encontrada"}), 404

    db.session.delete(tx)
    db.session.commit()
    return jsonify({"message": "Eliminada"}), 200
