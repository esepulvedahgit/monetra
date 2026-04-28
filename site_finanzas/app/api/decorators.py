from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models import User


def api_login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({"error": "Token inválido o expirado"}), 401
        user_id = get_jwt_identity()
        if not User.query.get(int(user_id)):
            return jsonify({"error": "Usuario no encontrado"}), 401
        return fn(*args, **kwargs)
    return wrapper


def get_current_api_user():
    user_id = get_jwt_identity()
    return User.query.get(int(user_id))
