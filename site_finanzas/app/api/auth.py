import re
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import request, jsonify, current_app, url_for
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
import pyotp
from app.models import MobileMfaChallenge, PasswordResetToken, User
from app.email_service import decrypt_mfa_secret, send_recovery_email
from app.api import api_v1
from app.api.schemas import user_schema
from app.api.decorators import (
    _account_error, _jwt_is_stale, api_login_required, get_current_api_user,
)
from app import db, limiter


def _token_pair(user):
    claims = {"session_version": user.api_session_version}
    return {
        "access_token": create_access_token(identity=str(user.id), additional_claims=claims),
        "refresh_token": create_refresh_token(identity=str(user.id), additional_claims=claims),
    }


def _current_refresh_user():
    """Return the owner of a non-revoked refresh token, or an API response."""
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return None, (jsonify({"error": "Token inválido o expirado"}), 401)
    account_error = _account_error(user)
    if account_error:
        return None, account_error
    if _jwt_is_stale(user):
        message = "La sesión ya no es válida"
        return None, (jsonify({"error": message, "code": "session_revoked", "message": message}), 401)
    return user, None


def _register_mobile_login_failure(user):
    """Apply the same account-level lockout policy used by the web login."""
    max_fails = current_app.config.get('LOGIN_MAX_FAILS', 3)
    lock_minutes = current_app.config.get('LOGIN_LOCK_MINUTES', 30)
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= max_fails:
        user.login_locked_until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
    db.session.commit()


def _locked_response():
    message = "Demasiados intentos fallidos. Intenta de nuevo en unos minutos."
    return jsonify({"error": message, "code": "account_locked", "message": message}), 429


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
    if user and user.login_is_locked:
        return _locked_response()
    if not user or not user.check_password(password):
        if user:
            _register_mobile_login_failure(user)
        return jsonify({"error": "Credenciales incorrectas"}), 401

    if user.is_suspended:
        return jsonify({
            "error": "Tu cuenta está suspendida. Contacta al administrador.",
            "code": "account_suspended",
            "message": "Tu cuenta está suspendida. Contacta al administrador.",
        }), 403

    if not user.email_verified:
        return jsonify({
            "error": "Tu cuenta aún no está activada.",
            "code": "email_unverified",
            "message": "Tu cuenta aún no está activada.",
        }), 403

    if user.mfa_enabled:
        raw_challenge = secrets.token_urlsafe(32)
        db.session.add(MobileMfaChallenge(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_challenge.encode()).hexdigest(),
            session_version=user.api_session_version,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        ))
        db.session.commit()
        return jsonify({
            "status": "mfa_required",
            "mfa_token": raw_challenge,
            "expires_in": 300,
        }), 202

    user.reset_login_lockout()
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({
        "status": "authenticated",
        **_token_pair(user),
        "user": user_schema(user),
    }), 200


@api_v1.post('/forgot-password')
@limiter.limit(lambda: current_app.config.get('FORGOT_PASSWORD_RATE_LIMIT', '3 per 15 minute'))
def forgot_password():
    """Request the existing web reset flow without disclosing account existence."""
    data = request.get_json(silent=True) or {}
    email = str(data.get('email', '')).strip().lower()
    user = User.query.filter_by(email=email).first() if email else None
    if user:
        admin = User.query.filter_by(is_first_admin=True).first()
        own_smtp = bool(user.email_config and user.email_config.smtp_enabled
                        and user.email_config.smtp_password_encrypted)
        admin_smtp = bool(admin and admin.id != user.id and admin.email_config
                          and admin.email_config.smtp_enabled
                          and admin.email_config.smtp_password_encrypted)
        if own_smtp or admin_smtp:
            PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).delete()
            raw_token = secrets.token_urlsafe(32)
            db.session.add(PasswordResetToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
                request_ip=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
            ))
            db.session.commit()
            reset_url = url_for('auth.reset_password', token=raw_token, _external=True)
            body = (
                "Hola,\n\nHas solicitado restablecer tu contraseña en Monetra.\n"
                f"Ingresa al siguiente enlace:\n{reset_url}\n\n"
                "Este enlace expira en 30 minutos. Si no fuiste tú, puedes ignorarlo."
            )
            send_recovery_email(user, user.email, "Recuperación de Contraseña - Monetra", body)

    message = "Si el correo existe y hay un SMTP disponible, recibirás las instrucciones."
    return jsonify({"message": message, "status": "accepted"}), 202


@api_v1.post('/refresh')
@jwt_required(refresh=True)
def refresh():
    user, error = _current_refresh_user()
    if error:
        return error

    # A refresh token may be used exactly once. Advancing the per-user session
    # version invalidates its predecessor and every access token in that chain.
    user.api_session_version += 1
    user.api_sessions_valid_after = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(_token_pair(user)), 200


@api_v1.post('/logout')
@jwt_required(refresh=True)
def logout():
    user, error = _current_refresh_user()
    if error:
        return error
    user.api_session_version += 1
    user.api_sessions_valid_after = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "ok"}), 200


@api_v1.get('/me')
@api_login_required
def me():
    user = get_current_api_user()
    return jsonify(user_schema(user)), 200


@api_v1.post('/mfa/verify')
@limiter.limit(lambda: current_app.config.get('MFA_VERIFY_RATE_LIMIT', '5 per minute'))
def verify_mfa():
    data = request.get_json(silent=True) or {}
    token_hash = hashlib.sha256(str(data.get('mfa_token', '')).encode()).hexdigest()
    challenge = MobileMfaChallenge.query.filter_by(token_hash=token_hash).first()
    user = db.session.get(User, challenge.user_id) if challenge else None
    expires_at = challenge.expires_at if challenge else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (not user or not challenge or challenge.consumed_at or expires_at < datetime.now(timezone.utc)
            or not user.mfa_enabled or user.api_session_version != challenge.session_version):
        message = "El desafío MFA no es válido o expiró"
        return jsonify({"error": message, "code": "mfa_challenge_invalid", "message": message}), 401
    if user.login_is_locked:
        return _locked_response()
    if user.is_suspended or not user.email_verified:
        message = "La cuenta no puede iniciar sesión"
        return jsonify({"error": message, "code": "account_unavailable", "message": message}), 403
    code = str(data.get('code', '')).strip()
    secret = decrypt_mfa_secret(user.mfa_secret_encrypted)
    if not pyotp.TOTP(secret).verify(code):
        _register_mobile_login_failure(user)
        message = "Código MFA incorrecto"
        return jsonify({"error": message, "code": "invalid_mfa_code", "message": message}), 401
    challenge.consumed_at = datetime.now(timezone.utc)
    user.reset_login_lockout()
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"status": "authenticated", **_token_pair(user), "user": user_schema(user)}), 200


def _password_error(password):
    if not isinstance(password, str) or len(password) < 10:
        return "La contraseña debe tener al menos 10 caracteres."
    if not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password):
        return "La contraseña debe incluir mayúsculas y minúsculas."
    if not re.search(r"\d", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "La contraseña debe incluir un número y un carácter especial."
    return None


@api_v1.post('/me/password')
@api_login_required
def change_password():
    user = get_current_api_user()
    data = request.get_json(silent=True) or {}
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not user.check_password(current_password):
        message = "Contraseña actual incorrecta"
        return jsonify({"error": message, "code": "invalid_current_password", "message": message}), 400
    if new_password != confirm_password:
        message = "Las contraseñas no coinciden"
        return jsonify({"error": message, "code": "validation_error", "message": message,
                        "fields": {"confirm_password": "No coincide"}}), 400
    error = _password_error(new_password)
    if error:
        return jsonify({"error": error, "code": "validation_error", "message": error,
                        "fields": {"new_password": error}}), 400

    user.set_password(new_password)
    user.api_sessions_valid_after = datetime.now(timezone.utc)
    user.api_session_version += 1
    db.session.commit()
    return jsonify({"message": "Contraseña actualizada", "code": "password_changed"}), 200
