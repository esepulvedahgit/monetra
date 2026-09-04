from datetime import date as date_type
from decimal import Decimal, InvalidOperation

from flask import jsonify, request
from sqlalchemy import extract

from app import db
from app.api.decorators import api_login_required, get_current_api_user
from app.api.usd import usd_api
from app.api.usd.schemas import usd_transaction_schema
from app.models import UsdCategory, UsdTransaction


MAX_USD_AMOUNT = Decimal('9999999999.99')


def _parse_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite() or amount <= 0 or amount > MAX_USD_AMOUNT:
        return None
    if amount.as_tuple().exponent < -2:
        return None
    return amount


def _parse_date(value):
    try:
        return date_type.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _parse_category_id(value):
    if isinstance(value, bool):
        return None
    try:
        category_id = int(value)
    except (TypeError, ValueError):
        return None
    if category_id <= 0 or str(category_id) != str(value).strip():
        return None
    return category_id


def _owned_category(user_id, category_id):
    return UsdCategory.query.filter_by(id=category_id, user_id=user_id).first()


def _owned_transaction(user_id, tx_id):
    return UsdTransaction.query.filter_by(id=tx_id, user_id=user_id).first()


def _valid_description(value):
    return isinstance(value, str) and len(value) <= 200


def _transaction_or_404(user_id, tx_id):
    transaction = _owned_transaction(user_id, tx_id)
    if not transaction:
        return None, (jsonify({'error': 'Transacción no encontrada'}), 404)
    return transaction, None


@usd_api.get('/transactions')
@api_login_required
def list_usd_transactions():
    user = get_current_api_user()
    query = UsdTransaction.query.filter_by(user_id=user.id)

    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    category_id = request.args.get('category_id', type=int)
    if year:
        query = query.filter(extract('year', UsdTransaction.date) == year)
    if month:
        query = query.filter(extract('month', UsdTransaction.date) == month)
    if category_id:
        query = query.filter_by(category_id=category_id)

    transactions = query.order_by(
        UsdTransaction.date.desc(), UsdTransaction.id.desc()
    ).all()
    return jsonify({
        'transactions': [usd_transaction_schema(transaction) for transaction in transactions],
        'total': len(transactions),
    }), 200


@usd_api.post('/transactions')
@api_login_required
def create_usd_transaction():
    user = get_current_api_user()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Se requiere JSON'}), 400

    amount = _parse_amount(data.get('amount'))
    if amount is None:
        return jsonify({'error': 'Monto inválido'}), 400

    transaction_date = _parse_date(data.get('date'))
    if transaction_date is None:
        return jsonify({'error': 'Fecha inválida (use YYYY-MM-DD)'}), 400

    category_id = _parse_category_id(data.get('category_id'))
    category = _owned_category(user.id, category_id) if category_id else None
    if not category:
        return jsonify({'error': 'Categoría no encontrada'}), 400

    description = data.get('description', '')
    if not _valid_description(description):
        return jsonify({'error': 'Descripción inválida'}), 400

    transaction = UsdTransaction(
        user_id=user.id,
        category_id=category.id,
        amount=amount,
        date=transaction_date,
        description=description or None,
        is_demo=False,
    )
    db.session.add(transaction)
    db.session.commit()
    db.session.refresh(transaction)
    return jsonify(usd_transaction_schema(transaction)), 201


@usd_api.put('/transactions/<int:tx_id>')
@api_login_required
def update_usd_transaction(tx_id):
    user = get_current_api_user()
    transaction, error = _transaction_or_404(user.id, tx_id)
    if error:
        return error

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Se requiere JSON'}), 400

    if 'amount' in data:
        amount = _parse_amount(data['amount'])
        if amount is None:
            return jsonify({'error': 'Monto inválido'}), 400
        transaction.amount = amount

    if 'date' in data:
        transaction_date = _parse_date(data['date'])
        if transaction_date is None:
            return jsonify({'error': 'Fecha inválida (use YYYY-MM-DD)'}), 400
        transaction.date = transaction_date

    if 'description' in data:
        if not _valid_description(data['description']):
            return jsonify({'error': 'Descripción inválida'}), 400
        transaction.description = data['description'] or None

    if 'category_id' in data:
        category_id = _parse_category_id(data['category_id'])
        category = _owned_category(user.id, category_id) if category_id else None
        if not category:
            return jsonify({'error': 'Categoría no encontrada'}), 400
        transaction.category_id = category.id

    db.session.commit()
    return jsonify(usd_transaction_schema(transaction)), 200


@usd_api.delete('/transactions/<int:tx_id>')
@api_login_required
def delete_usd_transaction(tx_id):
    user = get_current_api_user()
    transaction, error = _transaction_or_404(user.id, tx_id)
    if error:
        return error

    db.session.delete(transaction)
    db.session.commit()
    return jsonify({'message': 'Eliminada'}), 200
