"""WebAuthn / Passkey routes for biometric authentication (Face ID, fingerprint, etc.).

Endpoints:
  GET  /auth/webauthn/check          — check if email has a registered passkey (public)
  POST /auth/webauthn/login/begin    — generate authentication challenge (public)
  POST /auth/webauthn/login/complete — verify and login (public)
  POST /auth/webauthn/register/begin    — generate registration challenge (login required)
  POST /auth/webauthn/register/complete — save passkey (login required)
  POST /auth/webauthn/delete            — remove passkey (login required)
"""

import base64

from flask import current_app, jsonify, request, session, url_for
from flask_login import current_user, login_required, login_user

import webauthn
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
# Public: check if email has a passkey (used by login page JS)
# ---------------------------------------------------------------------------

@auth.route('/webauthn/check', methods=['GET'])
@limiter.limit("30 per minute")
def webauthn_check():
    """Return {has_passkey: bool} for a given email. Does not reveal user existence."""
    email = (request.args.get('email') or '').strip().lower()
    has_passkey = False
    if email:
        user = User.query.filter_by(email=email).first()
        if user and user.webauthn_credential:
            has_passkey = True
    return jsonify({'has_passkey': has_passkey})


# ---------------------------------------------------------------------------
# Login: begin (generate challenge)
# ---------------------------------------------------------------------------

@auth.route('/webauthn/login/begin', methods=['POST'])
@limiter.limit("10 per minute")
def webauthn_login_begin():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()

    user = User.query.filter_by(email=email).first()
    if not user or not user.webauthn_credential:
        return jsonify({'error': 'Sin passkey registrado para este correo.'}), 404

    credential = user.webauthn_credential

    # credential_id is stored as base64url string — decode to bytes for the descriptor
    cred_id_bytes = base64.urlsafe_b64decode(
        credential.credential_id + '=' * (-len(credential.credential_id) % 4)
    )

    options = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=cred_id_bytes)
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    # Store challenge in session (single-use)
    session['webauthn_auth_challenge'] = _b64url(options.challenge)
    session['webauthn_auth_user_id'] = user.id

    return options_to_json(options), 200, {'Content-Type': 'application/json'}


# ---------------------------------------------------------------------------
# Login: complete (verify assertion)
# ---------------------------------------------------------------------------

@auth.route('/webauthn/login/complete', methods=['POST'])
@limiter.limit("10 per minute")
def webauthn_login_complete():
    challenge_b64 = session.pop('webauthn_auth_challenge', None)
    user_id = session.pop('webauthn_auth_user_id', None)

    if not challenge_b64 or not user_id:
        return jsonify({'error': 'Sesión de autenticación expirada. Intenta de nuevo.'}), 400

    user = db.session.get(User, user_id)
    if not user or not user.webauthn_credential:
        return jsonify({'error': 'Credencial no encontrada.'}), 400

    credential = user.webauthn_credential
    expected_challenge = base64.urlsafe_b64decode(
        challenge_b64 + '=' * (-len(challenge_b64) % 4)
    )

    try:
        verification = verify_authentication_response(
            credential=request.get_json(silent=True) or {},
            expected_challenge=expected_challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            credential_public_key=credential.public_key,
            credential_current_sign_count=credential.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:
        current_app.logger.warning('WebAuthn auth verification failed: %s', exc)
        return jsonify({'error': 'Error al verificar la biometría. Intenta de nuevo.'}), 400

    # Update sign count (anti-replay)
    credential.sign_count = verification.new_sign_count
    db.session.commit()

    login_user(user)
    return jsonify({'ok': True, 'redirect': url_for('main.dashboard')})


# ---------------------------------------------------------------------------
# Register: begin (login required)
# ---------------------------------------------------------------------------

@auth.route('/webauthn/register/begin', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def webauthn_register_begin():
    user = current_user

    # Exclude existing credential if re-registering (replace flow)
    exclude = []
    if user.webauthn_credential:
        existing_cred_id = user.webauthn_credential.credential_id
        existing_cred_id_bytes = base64.urlsafe_b64decode(
            existing_cred_id + '=' * (-len(existing_cred_id) % 4)
        )
        exclude.append(PublicKeyCredentialDescriptor(id=existing_cred_id_bytes))

    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name=_rp_name(),
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
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
        device_name = 'iPhone / iPad'
    elif 'Android' in ua:
        device_name = 'Android'
    elif 'Macintosh' in ua:
        device_name = 'Mac'
    elif 'Windows' in ua:
        device_name = 'Windows'
    else:
        device_name = 'Dispositivo'

    # Upsert: one row per user (replace if exists)
    cred = current_user.webauthn_credential
    if cred:
        cred.credential_id = _b64url(verification.credential_id)
        cred.public_key    = verification.credential_public_key
        cred.sign_count    = verification.sign_count
        cred.device_name   = device_name
        from datetime import datetime, timezone
        cred.created_at    = datetime.now(timezone.utc)
    else:
        cred = UserWebAuthnCredential(
            user_id=current_user.id,
            credential_id=_b64url(verification.credential_id),
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            device_name=device_name,
        )
        db.session.add(cred)

    db.session.commit()
    return jsonify({'ok': True, 'device_name': device_name})


# ---------------------------------------------------------------------------
# Delete passkey (login required)
# ---------------------------------------------------------------------------

@auth.route('/webauthn/delete', methods=['POST'])
@login_required
def webauthn_delete():
    cred = current_user.webauthn_credential
    if cred:
        db.session.delete(cred)
        db.session.commit()
    return jsonify({'ok': True})
