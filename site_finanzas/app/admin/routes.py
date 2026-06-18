"""Admin user management — list, suspend/reactivate, delete.

Gate: is_admin AND is_first_admin (same as backup/restore — most sensitive operations).
Protections:
  - Cannot act on yourself.
  - Cannot act on any other is_first_admin account.
  - Delete requires re-entering the admin's own password.
  - All actions are audit-logged and notify the affected user by email (best-effort).
"""

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app import db
from app.admin import admin_bp
from app.models import User
from app.email_service import send_security_alert_email, send_security_alert_email_async
from app.audit.logger import log_event
from app.audit import events as ev


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin_required():
    """Abort with 403 unless caller is authenticated first-admin."""
    if not current_user.is_authenticated:
        abort(401)
    if not (current_user.is_admin and current_user.is_first_admin):
        abort(403)


def _audit(event_type, description=None):
    """Log an audit event silently (never breaks the calling flow)."""
    try:
        log_event(event_type, description=description,
                  user_id=current_user.id, request=request)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.error('Audit log failed for %s', event_type, exc_info=True)


# ---------------------------------------------------------------------------
# GET /admin/users/  — user list
# ---------------------------------------------------------------------------

@admin_bp.route('/')
@login_required
def index():
    _admin_required()
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html',
                           users=users,
                           title=_('Gestión de usuarios'))


# ---------------------------------------------------------------------------
# POST /admin/users/<id>/suspend  — toggle suspended flag
# ---------------------------------------------------------------------------

@admin_bp.route('/<int:user_id>/suspend', methods=['POST'])
@login_required
def suspend(user_id):
    _admin_required()
    user = db.session.get(User, user_id) or abort(404)

    if user.id == current_user.id:
        flash(_('No puedes suspender tu propia cuenta.'), 'danger')
        return redirect(url_for('admin.index'))
    if user.is_first_admin:
        flash(_('El administrador principal no puede ser suspendido.'), 'danger')
        return redirect(url_for('admin.index'))

    user.is_suspended = not user.is_suspended
    db.session.commit()

    if user.is_suspended:
        event_type  = ev.ADMIN_ACCOUNT_SUSPENDED
        action_label = _('tu cuenta fue suspendida por el administrador')
        flash(_('Usuario %(name)s suspendido.', name=user.username), 'warning')
    else:
        event_type   = ev.ADMIN_ACCOUNT_REACTIVATED
        action_label = _('tu cuenta fue reactivada por el administrador')
        flash(_('Usuario %(name)s reactivado.', name=user.username), 'success')

    _audit(event_type,
           description=f'{user.email} | by {current_user.email}')

    send_security_alert_email_async(user, action_label)

    return redirect(url_for('admin.index'))


# ---------------------------------------------------------------------------
# POST /admin/users/<id>/delete  — permanent deletion (requires admin password)
# ---------------------------------------------------------------------------

@admin_bp.route('/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    _admin_required()
    user = db.session.get(User, user_id) or abort(404)

    if user.id == current_user.id:
        flash(_('No puedes eliminar tu propia cuenta.'), 'danger')
        return redirect(url_for('admin.index'))
    if user.is_first_admin:
        flash(_('El administrador principal no puede ser eliminado.'), 'danger')
        return redirect(url_for('admin.index'))

    password = request.form.get('password', '')
    if not password or not current_user.check_password(password):
        flash(_('Contraseña incorrecta. El usuario no fue eliminado.'), 'danger')
        return redirect(url_for('admin.index'))

    # Capture identity before deletion (needed for audit + flash after commit)
    email_copy    = user.email
    username_copy = user.username
    user_id_copy  = user.id

    # Notify user BEFORE deleting so we can still use their email config / SMTP
    try:
        send_security_alert_email(user, _('tu cuenta fue eliminada por el administrador'))
    except Exception:
        pass

    # Explicit ApiToken deletion — the backref has cascade now, but belt-and-suspenders
    if user.api_token:
        db.session.delete(user.api_token)

    db.session.delete(user)
    db.session.commit()

    # Audit after commit (user_id in description since the user row is gone)
    _audit(ev.ADMIN_ACCOUNT_DELETED,
           description=f'user_id={user_id_copy} email={email_copy} | by {current_user.email}')

    flash(_('Usuario %(name)s eliminado permanentemente.', name=username_copy), 'success')
    return redirect(url_for('admin.index'))
