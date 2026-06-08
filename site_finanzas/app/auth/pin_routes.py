"""PIN de acceso rápido — método de login opt-in para dispositivos de confianza.

El PIN es un método de acceso independiente (no un fallback). Solo funciona:
  - en un dispositivo autorizado al configurar el PIN (identificado por una cookie
    httpOnly cuyo token se almacena hasheado en user_pin_devices), y
  - en modo responsive (< 992 px). La restricción es client-side; server-side el
    endpoint no distingue viewport, por diseño.

Endpoints (all under /pin/):
  POST set     — establece/reemplaza el PIN y autoriza el dispositivo actual (login required)
  POST delete  — elimina el PIN y revoca todos los dispositivos (login required)
  POST login   — verifica el PIN usando la cookie del dispositivo; logea al usuario (public)
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
from app.email_service import send_security_alert_email


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COOKIE_NAME      = 'monetra_pin_device'
COOKIE_PATH      = '/pin'
COOKIE_DAYS      = 90
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
    """Exactly 8 digits and not a trivial sequence/repetition."""
    if not pin or len(pin) != 8 or not pin.isdigit():
        return False
    if len(set(pin)) == 1:                        # 00000000, 11111111, ...
        return False
    asc = ''.join(str((int(pin[0]) + i) % 10) for i in range(8))
    desc = ''.join(str((int(pin[0]) - i) % 10) for i in range(8))
    if pin in (asc, desc):                        # 12345678, 87654321, wrap-arounds
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
        return jsonify({'error': 'El PIN debe tener 8 dígitos y no ser una secuencia obvia.'}), 400

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

    _audit(ev.AUTH_PIN_ENABLED, description=f'{current_user.email} activó PIN de acceso rápido',
           user_id=current_user.id)
    send_security_alert_email(current_user, "activó el PIN de acceso rápido")

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

    _audit(ev.AUTH_PIN_DISABLED, description=f'{current_user.email} desactivó PIN de acceso rápido',
           user_id=current_user.id)
    send_security_alert_email(current_user, "desactivó el PIN de acceso rápido")

    resp = jsonify({'ok': True})
    _clear_device_cookie(resp)
    return resp


# ---------------------------------------------------------------------------
# Login with PIN (public) — identity comes from the device cookie
# ---------------------------------------------------------------------------

@auth.route('/pin/login', methods=['POST'])
@limiter.limit("5 per minute")
def pin_login():
    # 1. Identify the device from the cookie
    raw_token = request.cookies.get(COOKIE_NAME, '')
    if not raw_token:
        return jsonify({'error': 'PIN no disponible en este dispositivo.'}), 403

    device = UserPinDevice.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if not device:
        return jsonify({'error': 'PIN no disponible en este dispositivo.'}), 403

    # 2. Expiry check (absolute)
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

    # 3. Account-level lockout
    if user.pin_is_locked:
        return jsonify({'error': 'Demasiados intentos. Usa tu contraseña.'}), 429

    # 4. Verify the PIN
    data = request.get_json(silent=True) or {}
    pin = (data.get('pin') or '').strip()
    if not user.check_pin(pin):
        user.pin_failed_attempts = (user.pin_failed_attempts or 0) + 1
        if user.pin_failed_attempts >= MAX_FAILS:
            user.pin_locked_until = _utcnow() + timedelta(minutes=LOCK_MINUTES)
        db.session.commit()
        _audit(ev.AUTH_LOGIN_FAIL, description=f'{user.email} (PIN)')
        return jsonify({'error': 'PIN incorrecto.'}), 403

    # 5. Success — reset counters, rotate the device token
    user.pin_failed_attempts = 0
    user.pin_locked_until = None
    device.last_used_at = _utcnow()
    new_token = secrets.token_urlsafe(32)
    device.token_hash = _hash_token(new_token)   # rotation (expires_at unchanged)
    db.session.commit()

    # 6. Same post-auth checks as the password login flow
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
