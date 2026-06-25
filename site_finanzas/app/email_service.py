import os
import smtplib
import socket
import ssl
from datetime import date, timezone
from email.message import EmailMessage
from cryptography.fernet import Fernet

def get_fernet():
    key = os.environ.get('FIELD_ENCRYPTION_KEY')
    if not key:
        raise ValueError("FIELD_ENCRYPTION_KEY not configured. Cannot encrypt/decrypt SMTP passwords.")
    return Fernet(key.encode())

def encrypt_smtp_password(password: str) -> bytes:
    if not password:
        return b''
    f = get_fernet()
    return f.encrypt(password.encode('utf-8'))

def decrypt_smtp_password(encrypted_password: bytes) -> str:
    if not encrypted_password:
        return ""
    f = get_fernet()
    try:
        return f.decrypt(encrypted_password).decode('utf-8')
    except Exception:
        return ""

def encrypt_mfa_secret(secret: str) -> bytes:
    if not secret:
        return b''
    f = get_fernet()
    return f.encrypt(secret.encode('utf-8'))

def decrypt_mfa_secret(encrypted_secret: bytes) -> str:
    if not encrypted_secret:
        return ""
    f = get_fernet()
    try:
        return f.decrypt(encrypted_secret).decode('utf-8')
    except Exception:
        return ""

def encrypt_ai_token(token: str) -> bytes:
    if not token:
        return b''
    f = get_fernet()
    return f.encrypt(token.encode('utf-8'))

def decrypt_ai_token(encrypted_token: bytes) -> str:
    if not encrypted_token:
        return ""
    f = get_fernet()
    try:
        return f.decrypt(encrypted_token).decode('utf-8')
    except Exception:
        try:
            from flask import current_app
            current_app.logger.warning('AI token decryption failed (possible key rotation or corruption)')
        except Exception:
            pass
        return ""


def resolve_ai_config(user):
    """Devuelve el UserAIConfig efectivo para escanear recibos, o None.

    Orden de resolución:
      1. Config propia del usuario si está enabled y tiene token guardado.
      2. Config del primer admin si shared_globally=True y tiene token,
         PERO solo cuando el usuario tiene email verificado y no está suspendido
         (control de costos: cada escaneo consume cuota del proveedor del admin).
    """
    from app.models import User as _User

    own = getattr(user, 'ai_config', None)
    if own and own.enabled and own.api_token_encrypted:
        return own

    # Fallback compartido: solo cuentas verificadas, activas y con acceso concedido por el admin
    if (not getattr(user, 'email_verified', False)
            or getattr(user, 'is_suspended', False)
            or not getattr(user, 'ai_access_granted', False)):
        return None

    admin = _User.query.filter_by(is_first_admin=True).first()
    if admin and admin.id != user.id:
        admin_cfg = admin.ai_config
        if admin_cfg and admin_cfg.shared_globally and admin_cfg.api_token_encrypted:
            return admin_cfg

    return None


def consume_shared_ai_quota(user) -> bool:
    """Consume one scan from the user's daily shared-AI quota.

    Returns True when the scan is allowed and the counter was incremented.
    Returns False when the user has already reached the daily limit.

    Should only be called when the user is consuming the admin's shared key
    (not their own). The daily limit is read from the Flask app config key
    AI_SHARED_DAILY_LIMIT (default 25).

    Uses atomic SQL UPDATEs to avoid TOCTOU race conditions when multiple
    Telegram messages arrive concurrently for the same user.
    """
    from flask import current_app
    from sqlalchemy import or_
    from app import db
    from app.models import User as _User

    limit: int = current_app.config.get('AI_SHARED_DAILY_LIMIT', 25)
    today = date.today()  # server-local date (UTC in production)

    # Step 1: reset counter atomically if the day changed or is NULL (first use).
    # NULL != today evaluates to NULL in SQL (not TRUE), so IS NULL must be explicit.
    db.session.query(_User).filter(
        _User.id == user.id,
        or_(_User.shared_ai_scans_date != today, _User.shared_ai_scans_date.is_(None)),
    ).update(
        {'shared_ai_scans_date': today, 'shared_ai_scans_count': 0},
        synchronize_session=False,
    )

    # Step 2: conditional increment — only succeeds while under the limit
    rows = db.session.query(_User).filter(
        _User.id == user.id,
        _User.shared_ai_scans_date == today,
        _User.shared_ai_scans_count < limit,
    ).update(
        {'shared_ai_scans_count': _User.shared_ai_scans_count + 1},
        synchronize_session=False,
    )
    db.session.commit()
    db.session.refresh(user)
    return rows == 1


def _open_and_send(config, msg):
    """Abre la conexión SMTP, envía el mensaje y garantiza el cierre del socket."""
    password = decrypt_smtp_password(config.smtp_password_encrypted)
    if not password:
        return False, "Error al descifrar la contraseña SMTP."

    server = None
    try:
        if config.smtp_use_ssl:
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)

        server.ehlo()
        if config.smtp_use_tls and not config.smtp_use_ssl:
            server.starttls()
            server.ehlo()

        server.login(config.smtp_username, password)
        server.send_message(msg)
        return True, "Correo enviado correctamente."

    except smtplib.SMTPAuthenticationError:
        return False, "Error de autenticación SMTP. Verifica tu usuario y contraseña."
    except smtplib.SMTPException as e:
        return False, f"Error del servidor SMTP: {str(e)}"
    except (socket.timeout, TimeoutError):
        return False, (
            "Tiempo de espera agotado al conectar con el servidor SMTP. "
            "Revisa el host y el puerto, y la combinación TLS/SSL: "
            "usa SSL para el puerto 465, o TLS (STARTTLS) para el 587. "
            "También puede ser un firewall que bloquea la salida de correo."
        )
    except (ConnectionRefusedError, socket.gaierror) as e:
        return False, (
            f"No se pudo conectar al servidor SMTP ({str(e)}). "
            "Verifica que el host y el puerto sean correctos."
        )
    except ssl.SSLError as e:
        return False, (
            f"Error de cifrado SSL/TLS ({str(e)}). "
            "Verifica la combinación: puerto 465 → SSL, puerto 587 → TLS (STARTTLS)."
        )
    except Exception as e:
        return False, f"Error inesperado al enviar el correo: {str(e)}"
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def _send_with_config(config, to_email, subject, body_text, body_html=None):
    """Core SMTP send using a UserEmailConfig object."""
    if not config.smtp_password_encrypted:
        return False, "La configuración SMTP no tiene contraseña."

    msg = EmailMessage()
    msg['Subject'] = subject
    sender_name = config.sender_name or 'Monetra'
    sender_email = config.sender_email or config.smtp_username
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = to_email
    msg.set_content(body_text)

    if body_html:
        msg.add_alternative(body_html, subtype='html')

    return _open_and_send(config, msg)


def send_user_email(user, to_email, subject, body_text, body_html=None):
    """Sends email using only the user's own SMTP config. No fallback (used for test email)."""
    config = user.email_config
    if not config or not config.smtp_enabled:
        return False, "SMTP no está configurado o está inactivo."
    return _send_with_config(config, to_email, subject, body_text, body_html)


def send_recovery_email(user, to_email, subject, body_text, body_html=None):
    """
    Sends a recovery email using the user's own SMTP if enabled,
    or the admin's SMTP as a transparent fallback.
    """
    from app.models import User as _User

    config = user.email_config
    if config and config.smtp_enabled and config.smtp_password_encrypted:
        return _send_with_config(config, to_email, subject, body_text, body_html)

    admin = _User.query.filter_by(is_first_admin=True).first()
    if admin and admin.id != user.id:
        admin_config = admin.email_config
        if admin_config and admin_config.smtp_enabled and admin_config.smtp_password_encrypted:
            return _send_with_config(admin_config, to_email, subject, body_text, body_html)

    return False, "No hay configuración SMTP disponible para enviar el correo."


def send_activation_email(user, activation_url: str) -> tuple[bool, str]:
    """Send account activation email using admin SMTP as fallback."""
    subject = "Activa tu cuenta en Monetra"
    body_text = (
        f"Hola {user.username},\n\n"
        f"¡Gracias por registrarte en Monetra!\n\n"
        f"Para activar tu cuenta, ingresa al siguiente enlace:\n{activation_url}\n\n"
        f"Este enlace expira en 24 horas.\n"
        f"Si no creaste esta cuenta, puedes ignorar este correo de forma segura."
    )
    body_html = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#0f0f1a;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0f0f1a;padding:40px 0;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#1a1a2e;border-radius:12px;
                    border:1px solid rgba(0,200,150,0.20);overflow:hidden;">
        <tr>
          <td style="padding:32px 40px 24px;text-align:center;">
            <div style="font-size:2rem;margin-bottom:8px;">&#128274;</div>
            <h1 style="color:#00C896;font-size:1.4rem;margin:0 0 8px;">
              Activa tu cuenta
            </h1>
            <p style="color:#a0a0b0;font-size:.9rem;margin:0;">
              Hola <strong style="color:#e0e0f0;">{user.username}</strong>,
              solo falta un paso para empezar a usar Monetra.
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:0 40px 32px;text-align:center;">
            <a href="{activation_url}"
               style="display:inline-block;padding:14px 36px;
                      background:#00C896;color:#0f0f1a;
                      font-weight:700;font-size:1rem;
                      text-decoration:none;border-radius:8px;">
              Activar mi cuenta
            </a>
            <p style="color:#606070;font-size:.8rem;margin:24px 0 0;">
              Este enlace expira en 24 horas.<br>
              Si no creaste esta cuenta, ignora este correo.
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 40px;border-top:1px solid rgba(255,255,255,0.06);
                     text-align:center;">
            <p style="color:#404055;font-size:.75rem;margin:0;">
              Monetra &mdash; Finanzas personales
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return send_recovery_email(user, user.email, subject, body_text, body_html)


def send_security_alert_email(user, action_label: str, detail: str = None) -> None:
    """Send a security notification when the user changes a security setting.

    Best-effort: never raises — the alert is informational and must not interrupt
    the flow that triggered it (PIN activation, PIN deletion, password change).

    Uses send_recovery_email() so user SMTP → admin SMTP fallback is automatic.
    """
    from datetime import datetime

    try:
        ts = datetime.utcnow().strftime('%d/%m/%Y a las %H:%M UTC')
        subject = "Aviso de seguridad — Monetra"
        body_text = (
            f"Hola {user.username},\n\n"
            f"Se {action_label} en tu cuenta Monetra el {ts}.\n\n"
            f"Si no fuiste tú, cambia tu contraseña de inmediato.\n\n"
            f"Saludos,\nEquipo Monetra"
        )
        if detail:
            body_text = (
                f"Hola {user.username},\n\n"
                f"Se {action_label} en tu cuenta Monetra el {ts}.\n"
                f"Detalle: {detail}\n\n"
                f"Si no fuiste tú, cambia tu contraseña de inmediato.\n\n"
                f"Saludos,\nEquipo Monetra"
            )
        detail_row = f"""
            <p style="color:#a0a0b0;font-size:.85rem;margin:8px 0 0;">
              Detalle: {detail}
            </p>""" if detail else ""
        body_html = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#0f0f1a;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0f0f1a;padding:40px 0;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#1a1a2e;border-radius:12px;
                    border:1px solid rgba(0,200,150,0.20);overflow:hidden;">
        <tr>
          <td style="padding:32px 40px 24px;text-align:center;">
            <div style="font-size:2rem;margin-bottom:8px;">&#128275;</div>
            <h1 style="color:#00C896;font-size:1.4rem;margin:0 0 8px;">
              Aviso de seguridad
            </h1>
            <p style="color:#a0a0b0;font-size:.9rem;margin:0;">
              Hola <strong style="color:#e0e0f0;">{user.username}</strong>,
              se registró un cambio en tu cuenta.
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:0 40px 32px;text-align:center;">
            <div style="background:rgba(0,200,150,0.08);border:1px solid rgba(0,200,150,0.20);
                        border-radius:8px;padding:20px;">
              <p style="color:#e0e0f0;font-size:1rem;margin:0;">
                Se <strong>{action_label}</strong>
              </p>
              <p style="color:#a0a0b0;font-size:.85rem;margin:8px 0 0;">
                {ts}
              </p>{detail_row}
            </div>
            <p style="color:#606070;font-size:.8rem;margin:24px 0 0;">
              Si no fuiste tú, cambia tu contraseña de inmediato.
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 40px;border-top:1px solid rgba(255,255,255,0.06);
                     text-align:center;">
            <p style="color:#404055;font-size:.75rem;margin:0;">
              Monetra &mdash; Finanzas personales
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        send_recovery_email(user, user.email, subject, body_text, body_html)
    except Exception:
        pass  # Best-effort — never break the caller


def send_security_alert_email_async(user, action_label: str, detail: str = None) -> None:
    """Fires send_security_alert_email in a daemon thread so the request is not blocked.

    Uses the same pattern as send_report_now in main/routes.py:
    - Captures app and user_id before the thread starts (safe across request contexts).
    - Re-fetches the User inside app_context() to avoid detached-instance errors.
    - The underlying call is already best-effort (never raises), so the thread is fire-and-forget.
    """
    import threading
    from flask import current_app

    app = current_app._get_current_object()
    user_id = user.id

    def _run():
        from app.models import User
        with app.app_context():
            u = User.query.get(user_id)
            if u is not None:
                send_security_alert_email(u, action_label, detail)

    threading.Thread(target=_run, daemon=True).start()


def send_weekly_report(user, excel_bytes: bytes, filename: str):
    """
    Sends the weekly Excel report to the user.
    Uses user's own SMTP if enabled, otherwise falls back to admin SMTP.
    Returns (bool, str) — same convention as other send_* functions.
    """
    from app.models import User as _User

    smtp_config = None
    config = user.email_config
    if config and config.smtp_enabled and config.smtp_password_encrypted:
        smtp_config = config
    else:
        admin = _User.query.filter_by(is_first_admin=True).first()
        if admin and admin.id != user.id:
            admin_config = admin.email_config
            if admin_config and admin_config.smtp_enabled and admin_config.smtp_password_encrypted:
                smtp_config = admin_config

    if smtp_config is None:
        return False, "No hay configuración SMTP disponible para enviar el reporte."

    from datetime import date
    today = date.today()
    subject = f"Monetra — Reporte semanal {today.strftime('%d/%m/%Y')}"
    body_text = (
        f"Hola {user.username},\n\n"
        f"Adjunto encontrarás tu reporte financiero semanal de Monetra.\n"
        f"Período: {today.strftime('%B %Y')}.\n\n"
        f"Saludos,\nEquipo Monetra"
    )

    msg = EmailMessage()
    msg['Subject'] = subject
    sender_name = smtp_config.sender_name or 'Monetra'
    sender_email = smtp_config.sender_email or smtp_config.smtp_username
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = user.email
    msg.set_content(body_text)
    msg.add_attachment(
        excel_bytes,
        maintype='application',
        subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        filename=filename,
    )

    ok, err_msg = _open_and_send(smtp_config, msg)
    if ok:
        return True, "Reporte enviado correctamente."
    return False, err_msg
