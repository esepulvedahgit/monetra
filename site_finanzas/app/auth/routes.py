import secrets
import hashlib
from datetime import datetime, timezone, timedelta
import pyotp
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user
from flask_babel import gettext as _
from app import db, limiter
from app.models import User, AppConfig, PasswordResetToken
from app.auth import auth
from app.auth.forms import LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm, MFAVerifyForm
from app.email_service import send_user_email, send_recovery_email, decrypt_mfa_secret
from app.audit.logger import log_event
from app.audit import events as ev


def _audit_commit(event_type, description=None, user_id=None):
    try:
        log_event(event_type, description=description, user_id=user_id, request=request)
        db.session.commit()
    except Exception:
        db.session.rollback()


@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    user_count = User.query.count()
    app_config = AppConfig.get()

    if user_count > 0 and not app_config.allow_registration:
        return render_template('auth/register.html', title=_('Registro'),
                               form=None, registration_blocked=True)

    form = RegisterForm()
    if form.validate_on_submit():
        is_first = user_count == 0
        user = User(
            username=form.username.data,
            email=form.email.data,
            role='admin' if is_first else 'user',
            is_first_admin=is_first,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        log_event(ev.AUTH_REGISTER, description=form.email.data, request=request)
        db.session.commit()
        flash(_('Cuenta creada exitosamente. Ya puedes iniciar sesión.'), 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', title=_('Registro'),
                           form=form, registration_blocked=False)


@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            if user.mfa_enabled:
                session['mfa_pending'] = {'user_id': user.id, 'remember': form.remember.data}
                return redirect(url_for('auth.mfa_verify'))
            login_user(user, remember=form.remember.data)
            _audit_commit(ev.AUTH_LOGIN_SUCCESS, description=user.email, user_id=user.id)
            flash(_('¡Bienvenido, %(username)s!', username=user.username), 'success')
            return redirect(url_for('main.dashboard'))
        _audit_commit(ev.AUTH_LOGIN_FAIL, description=form.email.data)
        flash(_('Email o contraseña incorrectos.'), 'danger')
    return render_template('auth/login.html', title=_('Iniciar Sesión'), form=form)


@auth.route('/mfa-verify', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def mfa_verify():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    pending = session.get('mfa_pending')
    if not pending:
        return redirect(url_for('auth.login'))
    form = MFAVerifyForm()
    if form.validate_on_submit():
        user = db.session.get(User, pending['user_id'])
        if user and user.mfa_enabled:
            secret = decrypt_mfa_secret(user.mfa_secret_encrypted)
            totp = pyotp.TOTP(secret)
            if totp.verify(form.code.data):
                session.pop('mfa_pending', None)
                login_user(user, remember=pending.get('remember', False))
                _audit_commit(ev.AUTH_LOGIN_SUCCESS, description=f'{user.email} (MFA)', user_id=user.id)
                flash(_('¡Bienvenido, %(username)s!', username=user.username), 'success')
                return redirect(url_for('main.dashboard'))
        _audit_commit(ev.AUTH_LOGIN_FAIL, description='MFA code invalid')
        flash(_('Código incorrecto. Inténtalo de nuevo.'), 'danger')
    return render_template('auth/mfa_verify.html', title=_('Verificación en dos pasos'), form=form)


@auth.route('/logout')
def logout():
    uid = current_user.id if current_user.is_authenticated else None
    _audit_commit(ev.AUTH_LOGOUT, user_id=uid)
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("3 per 15 minute", methods=['POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            admin = User.query.filter_by(is_first_admin=True).first()
            user_smtp_ok = bool(
                user.email_config and user.email_config.smtp_enabled
                and user.email_config.smtp_password_encrypted
            )
            admin_smtp_ok = bool(
                admin and admin.id != user.id
                and admin.email_config and admin.email_config.smtp_enabled
                and admin.email_config.smtp_password_encrypted
            )
            if user_smtp_ok or admin_smtp_ok:
                PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).delete()

                raw_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
                expires = datetime.now(timezone.utc) + timedelta(minutes=30)

                token_record = PasswordResetToken(
                    user_id=user.id,
                    token_hash=token_hash,
                    expires_at=expires,
                    request_ip=request.remote_addr,
                    user_agent=request.headers.get('User-Agent')
                )
                db.session.add(token_record)
                db.session.commit()

                reset_url = url_for('auth.reset_password', token=raw_token, _external=True)
                body_text = (
                    f"Hola,\n\nHas solicitado restablecer tu contraseña en Monetra.\n"
                    f"Ingresa al siguiente enlace:\n{reset_url}\n\n"
                    f"Este enlace expira en 30 minutos.\n"
                    f"Si no fuiste tú, puedes ignorar este correo de forma segura."
                )
                send_recovery_email(user, user.email, "Recuperación de Contraseña - Monetra", body_text)

        flash(_('Si el correo existe y hay un SMTP disponible, recibirás las instrucciones en tu correo.'), 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', title=_('Recuperar Contraseña'), form=form)


@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minute", methods=['POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    token_record = PasswordResetToken.query.filter_by(token_hash=token_hash).first()

    if not token_record or token_record.used_at or token_record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        flash(_('El enlace de recuperación es inválido o ha expirado.'), 'danger')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.get(token_record.user_id)
        user.set_password(form.password.data)
        token_record.used_at = datetime.now(timezone.utc)

        PasswordResetToken.query.filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None)
        ).delete()

        log_event(ev.AUTH_PASSWORD_RESET_DONE, description=user.email,
                  user_id=user.id, request=request)
        db.session.commit()
        flash(_('Tu contraseña ha sido actualizada exitosamente.'), 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', title=_('Restablecer Contraseña'), form=form)
