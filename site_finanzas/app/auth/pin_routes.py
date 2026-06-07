"""Backup PIN routes — contextual fallback when Face ID fails.

The PIN is NOT a standalone login method. It only works:
  - on a device authorized at PIN setup (identified by an httpOnly cookie whose
    token is stored hashed in user_pin_devices), and
  - right after a biometric login attempt (session marker set in webauthn_login_begin).

Endpoints (all under /auth/pin/):
  POST set     — set/replace the PIN and authorize the current device (login required)
  POST delete  — remove the PIN and revoke all devices (login required)
  POST login   — verify PIN using the device cookie; logs the user in (public)
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app, jsonify, request, session, url_for
from flask_login import current_user, login_required, login_user

from app import db, limiter
from app.auth import auth
from app.models import User, UserPinDevice
from app.audit import events as ev
from app.audit.logger import log_event


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COOKIE_NAME      = 'monetra_pin_device'
COOKIE_PATH      = '/pin'
COOKIE_DAYS      = 90
ATTEMPT_WINDOW   = timedelta(minutes=5)   # PIN allowed only this long after a biometric attempt
MAX_FAILS        = 5
LOCK_MINUTES     = 15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow():
    """Naive UTC now — matches how MySQL DATETIME values round-trip."""
    return datetime.utcnow()


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _device_name():
    ua = request.headers.get('User-Agent', '')
    if 'iPhone' in ua or 'iPad' in ua:
        return 'iPhone / iPad'
    if 'Android' in ua:
        return 'Android'
    if 'Macintosh' in ua:
        return 'Mac'
    if 'Windows' in ua:
        return 'Windows'
    return 'Dispositivo'


def _set_device_cookie(response, raw_token: str):
    response.set_cookie(
        COOKIE_NAME,
        raw_token,
        max_age=COOKIE_DAYS * 24 * 3600,
        httponly=True,
        secure=request.is_secure,   # HTTPS in prod; allows http://localhost in dev
        samesite='Strict',
        path=COOKIE_PATH,
    )


def _clear_device_cookie(response):
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)


def _audit(event_type, description=None, user_id=None):
    try:
        log_event(event_type, description=description, user_id=user_id, request=request)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _is_valid_pin(pin: str) -> bool:
    """Exactly 6 digits and not a trivial sequence/repetition."""
    if not pin or len(pin) != 6 or not pin.isdigit():
        return False
    if len(set(pin)) == 1:                       # 000000, 111111, ...
        return False
    asc = ''.join(str((int(pin[0]) + i) % 10) for i in range(6))
    desc = ''.join(str((int(pin[0]) - i) % 10) for i in range(6))
    if pin in (asc, desc):                        # 123456, 654321, wrap-arounds
        return False
    if pin in ('123456', '654321', '012345', '111111'):
        return False
    return True


# ---------------------------------------------------------------------------
# Set / replace PIN (login required) — authorizes the current device
# ---------------------------------------------------------------------------

@auth.route('/pin/set', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def pin_set():
    data = request.get_json(silent=True) or {}
    password = data.get('password', '')
    pin = (data.get('pin') or '').strip()

    if not password or not current_user.check_password(password):
        return jsonify({'error': 'Contraseña incorrecta.'}), 403

    if not _is_valid_pin(pin):
        return jsonify({'error': 'El PIN debe tener 6 dígitos y no ser una secuencia obvia.'}), 400

    # Set PIN and clear any lockout state
    current_user.set_pin(pin)
    current_user.pin_failed_attempts = 0
    current_user.pin_locked_until = None

    # Authorize this device: store hash, hand raw token to the cookie
    raw_token = secrets.token_urlsafe(32)
    device = UserPinDevice(
        user_id=current_user.id,
        token_hash=_hash_token(raw_token),
        device_name=_device_name(),
        created_at=_utcnow(),
        expires_at=_utcnow() + timedelta(days=COOKIE_DAYS),
    )
    db.session.add(device)
    db.session.commit()

    resp = jsonify({'ok': True})
    _set_device_cookie(resp, raw_token)
    return resp


# ---------------------------------------------------------------------------
# Delete PIN (login required) — revokes all authorized devices
# ---------------------------------------------------------------------------

@auth.route('/pin/delete', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def pin_delete():
    data = request.get_json(silent=True) or {}
    password = data.get('password', '')
    if not password or not current_user.check_password(password):
        return jsonify({'error': 'Contraseña incorrecta.'}), 403

    current_user.pin_hash = None
    current_user.pin_failed_attempts = 0
    current_user.pin_locked_until = None
    UserPinDevice.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

    resp = jsonify({'ok': True})
    _clear_device_cookie(resp)
    return resp


# ---------------------------------------------------------------------------
# Login with PIN (public) — identity comes from the device cookie
# ---------------------------------------------------------------------------

@auth.route('/pin/login', methods=['POST'])
@limiter.limit("5 per minute")
def pin_login():
    # 1. Must follow a recent biometric attempt — the PIN is a fallback, not a fixed door.
    attempt_at = session.get('biometric_attempt_at')
    if not attempt_at:
        return jsonify({'error': 'Inicia con Face ID primero.'}), 403
    try:
        attempted = datetime.fromisoformat(attempt_at)
        if attempted.tzinfo is not None:
            attempted = attempted.replace(tzinfo=None)
    except (ValueError, TypeError):
        return jsonify({'error': 'Inicia con Face ID primero.'}), 403
    if _utcnow() - attempted > ATTEMPT_WINDOW:
        session.pop('biometric_attempt_at', None)
        return jsonify({'error': 'Inicia con Face ID primero.'}), 403

    # 2. Identify the device from the cookie
    raw_token = request.cookies.get(COOKIE_NAME, '')
    if not raw_token:
        return jsonify({'error': 'PIN no disponible en este dispositivo.'}), 403

    device = UserPinDevice.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if not device:
        return jsonify({'error': 'PIN no disponible en este dispositivo.'}), 403

    # 3. Expiry check (absolute)
    expires_at = device.expires_at
    if expires_at and expires_at.tzinfo is not None:
        expires_at = expires_at.replace(tzinfo=None)
    if not expires_at or expires_at <= _utcnow():
        db.session.delete(device)
        db.session.commit()
        resp = jsonify({'error': 'El PIN expiró en este dispositivo. Vuelve a configurarlo.'})
        _clear_device_cookie(resp)
        return resp, 403

    user = device.user
    if not user or not user.has_pin:
        return jsonify({'error': 'PIN no disponible en este dispositivo.'}), 403

    # 4. Account-level lockout
    if user.pin_is_locked:
        return jsonify({'error': 'Demasiados intentos. Usa tu contraseña.'}), 429

    # 5. Verify the PIN
    data = request.get_json(silent=True) or {}
    pin = (data.get('pin') or '').strip()
    if not user.check_pin(pin):
        user.pin_failed_attempts = (user.pin_failed_attempts or 0) + 1
        if user.pin_failed_attempts >= MAX_FAILS:
            user.pin_locked_until = _utcnow() + timedelta(minutes=LOCK_MINUTES)
        db.session.commit()
        _audit(ev.AUTH_LOGIN_FAIL, description=f'{user.email} (PIN)')
        return jsonify({'error': 'PIN incorrecto.'}), 403

    # 6. Success — reset counters, rotate the device token, consume the biometric marker
    user.pin_failed_attempts = 0
    user.pin_locked_until = None
    device.last_used_at = _utcnow()
    new_token = secrets.token_urlsafe(32)
    device.token_hash = _hash_token(new_token)   # rotation (expires_at unchanged)
    db.session.commit()
    session.pop('biometric_attempt_at', None)

    # 7. Same post-auth checks as the password login flow
    if not user.email_verified:
        return jsonify({'error': 'Tu cuenta aún no está activada. Revisa tu correo.'}), 403

    if user.mfa_enabled:
        session['mfa_pending'] = {'user_id': user.id, 'remember': False}
        resp = jsonify({'ok': True, 'redirect': url_for('auth.mfa_verify')})
        _set_device_cookie(resp, new_token)
        return resp

    login_user(user)
    session['_login_at'] = datetime.now(timezone.utc).isoformat()
    _audit(ev.AUTH_LOGIN_SUCCESS, description=f'{user.email} (PIN)', user_id=user.id)

    resp = jsonify({'ok': True, 'redirect': url_for('main.dashboard')})
    _set_device_cookie(resp, new_token)
    return resp
