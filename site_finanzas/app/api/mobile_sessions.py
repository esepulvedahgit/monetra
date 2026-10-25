"""Sesiones móviles por dispositivo (ver models.MobileSession).

Los tokens emitidos antes de existir estas sesiones no traen ``sid`` y siguen
validándose con la versión de sesión del usuario hasta su siguiente renovación,
que los migra a una sesión propia.
"""
import secrets
from datetime import datetime, timezone

from flask_jwt_extended import get_jwt

from app import db
from app.models import MobileSession


def _now():
    return datetime.now(timezone.utc)


def start_session(user) -> MobileSession:
    session = MobileSession(user_id=user.id, public_id=secrets.token_hex(16), version=0, last_used_at=_now())
    db.session.add(session)
    db.session.flush()
    return session


def claims_for(session: MobileSession) -> dict:
    return {"sid": session.public_id, "sv": session.version}


def token_session(user):
    """Sesión del JWT en curso: None si es un token antiguo sin ``sid``; False si ya no es válida."""
    jwt = get_jwt()
    sid = jwt.get("sid")
    if sid is None:
        return None
    session = MobileSession.query.filter_by(public_id=sid, user_id=user.id).first()
    if session is None or session.revoked_at is not None or jwt.get("sv") != session.version:
        return False
    return session


def rotate(session: MobileSession) -> None:
    session.version += 1
    session.last_used_at = _now()


def revoke(session: MobileSession) -> None:
    session.revoked_at = _now()


def revoke_all(user) -> None:
    """Cierra la app en todos los dispositivos (cambio o recuperación de contraseña)."""
    MobileSession.query.filter_by(user_id=user.id, revoked_at=None).update({MobileSession.revoked_at: _now()})


def find_session(user):
    """Sesión del JWT en curso aunque esté desfasada, para cerrarla si se reusa un refresh token."""
    sid = get_jwt().get("sid")
    return MobileSession.query.filter_by(public_id=sid, user_id=user.id).first() if sid else None
