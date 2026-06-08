"""WebAuthn / Passkey routes for biometric authentication (Face ID, fingerprint, etc.).

Endpoints (all under /auth/webauthn/):
  POST login/begin    — generate authentication challenge; usernameless (no email needed)
  POST login/complete — verify assertion and log in; user identified by credential_id
  POST register/begin    — generate registration challenge (login required)
  POST register/complete — save discoverable passkey (login required)
  POST delete            — remove passkey (login required)
"""

import base64
from datetime import datetime, timezone

from flask import current_app, jsonify, request, session, url_for
from flask_login import current_user, login_required, login_user
from flask_wtf.csrf import validate_csrf, ValidationError as CSRFValidationError

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app import db, limiter
from app.auth import auth
from app.models import User, UserWebAuthnCredential


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rp_id():
    return current_app.config.get('WEBAUTHN_RP_ID', 'localhost')


def _rp_name():
    return current_app.config.get('WEBAUTHN_RP_NAME', 'Monetra')


def _origin():
    return current_app.config.get('WEBAUTHN_ORIGIN', 'http://localhost:5000')


def _b64url(data: bytes) -> str:
    """Encode bytes as URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


# ---------------------------------------------------------------------------
# Login: begin (generate challenge — usernameless / discoverable credentials)
# ---------------------------------------------------------------------------

@auth.route('/webauthn/login/begin', methods=['POST'])
@limiter.limit("10 per minute")
def webauthn_login_begin():
    """Generate an authentication challenge without requiring the user's email.

    We use discoverable credentials (resident keys): the browser presents all
    passkeys stored for this RP and the user picks one. The server identifies
    the user from the credential_id returned in login/complete.
    """
    options = generate_authentication_options(
        rp_id=_rp_id(),
        user_verification=UserVerificationRequirement.REQUIRED,
        # No allow_credentials → browser shows all passkeys for this domain
    )

    # Store challenge in session (single-use)
    session['webauthn_auth_challenge'] = _b64url(options.challenge)

    return options_to_json(options), 200, {'Content-Type': 'application/json'}


# ---------------------------------------------------------------------------
# Login: complete (verify assertion)
# ---------------------------------------------------------------------------

@auth.route('/webauthn/login/complete', methods=['POST'])
@limiter.limit("10 per minute")
def webauthn_login_complete():
    challenge_b64 = session.pop('webauthn_auth_challenge', None)

    if not challenge_b64:
        return jsonify({'error': 'Sesión de autenticación expirada. Intenta de nuevo.'}), 400

    body = request.get_json(silent=True) or {}

    # Identify user from credential_id returned by the browser (discoverable flow).
    # The browser returns id as base64url without padding — same format _b64url() produces.
    raw_id = (body.get('id') or '').strip()
    if not raw_id:
        return jsonify({'error': 'Credencial no reconocida.'}), 400

    credential = UserWebAuthnCredential.query.filter_by(credential_id=raw_id).first()
    if not credential:
        return jsonify({'error': 'Credencial no reconocida.'}), 400

    user = credential.user
    if not user:
        return jsonify({'error': 'Credencial no reconocida.'}), 400

    expected_challenge = base64.urlsafe_b64decode(
        challenge_b64 + '=' * (-len(challenge_b64) % 4)
    )

    try:
        verification = verify_authentication_response(
            credential=body,
            expected_challenge=expected_challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            credential_public_key=credential.public_key,
            credential_current_sign_count=credential.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:
        # py_webauthn raises if new_sign_count <= stored sign_count (both > 0),
        # which is the FIDO2 indicator of a cloned authenticator.
        exc_msg = str(exc).lower()
        if 'sign_count' in exc_msg or 'sign count' in exc_msg:
            current_app.logger.error(
                'WebAuthn: posible autenticador clonado — user_id=%s: %s', user.id, exc
            )
        else:
            current_app.logger.warning('WebAuthn auth verification failed: %s', exc)
        return jsonify({'error': 'Error al verificar la biometría. Intenta de nuevo.'}), 400

    # Update sign count (anti-replay) — must persist regardless of account state
    credential.sign_count = verification.new_sign_count
    db.session.commit()

    if not login_user(user):
        return jsonify({'error': 'Tu cuenta está suspendida. Contacta al administrador.'}), 403
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()
    session['_login_at'] = datetime.now(timezone.utc).isoformat()
    return jsonify({'ok': True, 'redirect': url_for('main.dashboard')})


# ---------------------------------------------------------------------------
# Register: begin (login required)
# ---------------------------------------------------------------------------

@auth.route('/webauthn/register/begin', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def webauthn_register_begin():
    user = current_user

    data = request.get_json(silent=True) or {}
    password = data.get('password', '')
    if not password or not user.check_password(password):
        return jsonify({'error': 'Contraseña incorrecta.'}), 403

    # Exclude all credentials already registered for this user so the browser
    # refuses to register the same authenticator twice.
    exclude = []
    for existing in user.webauthn_credentials:
        existing_cred_id_bytes = base64.urlsafe_b64decode(
            existing.credential_id + '=' * (-len(existing.credential_id) % 4)
        )
        exclude.append(PublicKeyCredentialDescriptor(id=existing_cred_id_bytes))

    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name=_rp_name(),
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=exclude,
    )

    session['webauthn_reg_challenge'] = _b64url(options.challenge)

    return options_to_json(options), 200, {'Content-Type': 'application/json'}


# ---------------------------------------------------------------------------
# Register: complete (login required)
# ---------------------------------------------------------------------------

@auth.route('/webauthn/register/complete', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def webauthn_register_complete():
    challenge_b64 = session.pop('webauthn_reg_challenge', None)
    if not challenge_b64:
        return jsonify({'error': 'Sesión de registro expirada. Intenta de nuevo.'}), 400

    expected_challenge = base64.urlsafe_b64decode(
        challenge_b64 + '=' * (-len(challenge_b64) % 4)
    )

    try:
        verification = verify_registration_response(
            credential=request.get_json(silent=True) or {},
            expected_challenge=expected_challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            require_user_verification=True,
        )
    except Exception as exc:
        current_app.logger.warning('WebAuthn registration verification failed: %s', exc)
        return jsonify({'error': 'Error al registrar el dispositivo. Intenta de nuevo.'}), 400

    # Infer device name from User-Agent
    ua = request.headers.get('User-Agent', '')
    if 'iPhone' in ua or 'iPad' in ua:
        base_name = 'iPhone / iPad'
    elif 'Android' in ua:
        base_name = 'Android'
    elif 'Macintosh' in ua:
        base_name = 'Mac'
    elif 'Windows' in ua:
        base_name = 'Windows'
    else:
        base_name = 'Dispositivo'

    # Disambiguate name if the user already has a credential with the same base name.
    existing_names = {c.device_name for c in current_user.webauthn_credentials}
    from datetime import datetime, timezone
    if base_name in existing_names:
        device_name = f'{base_name} ({datetime.now(timezone.utc).strftime("%d %b %Y")})'
    else:
        device_name = base_name

    # Always insert a new credential — multiple credentials per user are allowed.
    cred = UserWebAuthnCredential(
        user_id=current_user.id,
        credential_id=_b64url(verification.credential_id),
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        device_name=device_name,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(cred)
    db.session.commit()
    return jsonify({'ok': True, 'device_name': device_name})


# ---------------------------------------------------------------------------
# Delete passkey (login required)
# ---------------------------------------------------------------------------

@auth.route('/webauthn/delete', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def webauthn_delete():
    # Explicit CSRF check — belt-and-suspenders in case the global CSRFProtect
    # configuration ever changes for this blueprint.
    try:
        validate_csrf(request.headers.get('X-CSRFToken'))
    except CSRFValidationError:
        return jsonify({'error': 'Token CSRF inválido.'}), 403

    data = request.get_json(silent=True) or {}
    password = data.get('password', '')
    if not password or not current_user.check_password(password):
        return jsonify({'error': 'Contraseña incorrecta.'}), 403

    credential_id = (data.get('credential_id') or '').strip()
    if not credential_id:
        return jsonify({'error': 'Credencial no especificada.'}), 400

    # Verify ownership — never delete a credential that belongs to another user.
    cred = UserWebAuthnCredential.query.filter_by(
        credential_id=credential_id,
        user_id=current_user.id,
    ).first()
    if not cred:
        return jsonify({'error': 'Credencial no encontrada.'}), 404

    db.session.delete(cred)
    db.session.commit()

    # Tell the client how many credentials remain so it can update localStorage.
    remaining = len(current_user.webauthn_credentials)
    return jsonify({'ok': True, 'remaining': remaining})
