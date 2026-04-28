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


def _send_with_config(config, to_email, subject, body_text, body_html=None):
    """Core SMTP send using a UserEmailConfig object."""
    try:
        if not config.smtp_password_encrypted:
            return False, "La configuración SMTP no tiene contraseña."

        password = decrypt_smtp_password(config.smtp_password_encrypted)
        if not password:
            return False, "Error al descifrar la contraseña SMTP."

        msg = EmailMessage()
        msg['Subject'] = subject
        sender_name = config.sender_name or 'Monetra'
        sender_email = config.sender_email or config.smtp_username
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = to_email
        msg.set_content(body_text)

        if body_html:
            msg.add_alternative(body_html, subtype='html')

        host = config.smtp_host
        port = config.smtp_port

        if config.smtp_use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)

        server.ehlo()
        if config.smtp_use_tls and not config.smtp_use_ssl:
            server.starttls()
            server.ehlo()

        server.login(config.smtp_username, password)
        server.send_message(msg)
        server.quit()

        return True, "Correo enviado correctamente."

    except smtplib.SMTPAuthenticationError:
        return False, "Error de autenticación SMTP. Verifica tu usuario y contraseña."
    except smtplib.SMTPException as e:
        return False, f"Error del servidor SMTP: {str(e)}"
    except Exception as e:
        return False, f"Error inesperado al enviar el correo: {str(e)}"


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

    try:
        password = decrypt_smtp_password(smtp_config.smtp_password_encrypted)
        if not password:
            return False, "Error al descifrar la contraseña SMTP."

        from datetime import date
        today = date.today()
        subject = f"Monetra — Reporte semanal {today.strftime('%d/%m/%Y')}"
        body_text = (
            f"Hola {user.username},\n\n"
            f"Adjunto encontrarás tu reporte financiero semanal de Monetra.\n"
            f"Período: enero — {today.strftime('%B %Y')}.\n\n"
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

        host = smtp_config.smtp_host
        port = smtp_config.smtp_port
        if smtp_config.smtp_use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)

        server.ehlo()
        if smtp_config.smtp_use_tls and not smtp_config.smtp_use_ssl:
            server.starttls()
            server.ehlo()

        server.login(smtp_config.smtp_username, password)
        server.send_message(msg)
        server.quit()

        return True, "Reporte enviado correctamente."

    except smtplib.SMTPAuthenticationError:
        return False, "Error de autenticación SMTP."
    except smtplib.SMTPException as e:
        return False, f"Error del servidor SMTP: {str(e)}"
    except Exception as e:
        return False, f"Error inesperado: {str(e)}"
