import os
import smtplib
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
        return ""


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
