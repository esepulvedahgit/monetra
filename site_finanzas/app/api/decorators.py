import hashlib
from datetime import datetime, timezone
from functools import wraps
from flask import g, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from app.models import User, ApiToken
from app import db


def _account_error(user):
    if user.is_suspended:
        message = "Tu cuenta está suspendida. Contacta al administrador."
        return jsonify({"error": message, "code": "account_suspended", "message": message}), 403
    if not user.email_verified:
        message = "Tu cuenta aún no está activada."
        return jsonify({"error": message, "code": "email_unverified", "message": message}), 403
    return None


def _jwt_is_stale(user):
    token_version = get_jwt().get("session_version", 0)
    if token_version != getattr(user, "api_session_version", 0):
        return True
    valid_after = getattr(user, "api_sessions_valid_after", None)
    if valid_after is None:
        return False
    if valid_after.tzinfo is None:
        valid_after = valid_after.replace(tzinfo=timezone.utc)
    issued_at = get_jwt().get("iat")
    return issued_at is None or issued_at < int(valid_after.timestamp())


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
            account_error = _account_error(tok.user)
            if account_error:
                return account_error
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
        account_error = _account_error(user)
        if account_error:
            return account_error
        if _jwt_is_stale(user):
            message = "La sesión ya no es válida"
            return jsonify({"error": message, "code": "session_revoked", "message": message}), 401
        g.current_api_user = user
        return fn(*args, **kwargs)

    return wrapper


def get_current_api_user():
    return getattr(g, 'current_api_user', None)
