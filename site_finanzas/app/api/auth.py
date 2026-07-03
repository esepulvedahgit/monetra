from flask import request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from app.models import User
from app.api import api_v1
from app.api.schemas import user_schema
from app.api.decorators import api_login_required, get_current_api_user
from app import limiter


@api_v1.post('/login')
@limiter.limit(lambda: current_app.config.get('API_LOGIN_RATE_LIMIT', '5 per minute'))
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Se requiere JSON"}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"error": "Email y contraseña son requeridos"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Credenciales incorrectas"}), 401

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user_schema(user),
    }), 200


@api_v1.post('/refresh')
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({"access_token": access_token}), 200


@api_v1.post('/logout')
def logout():
    return jsonify({"message": "ok"}), 200


@api_v1.get('/me')
@api_login_required
def me():
    user = get_current_api_user()
    return jsonify(user_schema(user)), 200
