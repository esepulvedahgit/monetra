import hashlib
from datetime import datetime, timezone
from functools import wraps
from flask import g, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models import User, ApiToken
from app import db


def api_login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        raw = auth[7:].strip() if auth.startswith('Bearer ') else ''

        if raw.startswith('mntr_'):
            h = hashlib.sha256(raw.encode()).hexdigest()
            tok = ApiToken.query.filter_by(token_hash=h).first()
            if not tok:
                return jsonify({"error": "Token inválido o expirado"}), 401
            tok.last_used_at = datetime.now(timezone.utc)
            db.session.commit()
            g.current_api_user = tok.user
            return fn(*args, **kwargs)

        # fallback: JWT efímero (login de 15 min)
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({"error": "Token inválido o expirado"}), 401
        user = db.session.get(User, int(get_jwt_identity()))
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 401
        g.current_api_user = user
        return fn(*args, **kwargs)

    return wrapper


def get_current_api_user():
    return getattr(g, 'current_api_user', None)
