from datetime import datetime, timezone

from flask import current_app, request, redirect, url_for, flash, Response, abort, session
from flask_login import current_user, login_required, logout_user

from app import db, limiter
from app.backup import backup_bp
from app.backup.service import make_backup, read_backup, restore_database, _save_safety_snapshot
from app.models import AppConfig
from app.audit.logger import log_event
from app.audit import events as ev


def _admin_required():
    """Inline admin gate: must be first-admin. Aborts with 403 otherwise."""
    if not current_user.is_authenticated:
        abort(401)
    if not (current_user.is_admin and current_user.is_first_admin):
        abort(403)


# ── Export ────────────────────────────────────────────────────────────────────

@backup_bp.route('/export', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get('BACKUP_EXPORT_RATE_LIMIT', '5 per hour'), methods=['POST'])
def export_db():
    _admin_required()

    # Re-authentication: verify admin account password before exporting (H2 — mitigates
    # stolen-session attacks; a valid session alone must not be enough to export the DB).
    account_password = request.form.get('account_password', '')
    if not current_user.check_password(account_password):
        flash('Contraseña de la cuenta incorrecta. La exportación fue cancelada.', 'danger')
        return redirect(url_for('main.configurar'))

    backup_password = request.form.get('backup_password', '').strip()
    backup_password_confirm = request.form.get('backup_password_confirm', '').strip()

    if not backup_password:
        flash('La contraseña del respaldo no puede estar vacía.', 'danger')
        return redirect(url_for('main.configurar'))

    # H8: server-side password confirmation check
    if backup_password != backup_password_confirm:
        flash('Las contraseñas del respaldo no coinciden.', 'danger')
        return redirect(url_for('main.configurar'))

    try:
        blob = make_backup(backup_password)
    except Exception:
        # H3: never expose exc details (may contain DB host/user from mysqldump stderr)
        current_app.logger.exception('DB backup export failed (user_id=%s)', current_user.id)
        flash('No se pudo generar el respaldo. Revisa los registros del servidor.', 'danger')
        return redirect(url_for('main.configurar'))

    try:
        log_event(
            ev.ADMIN_DB_EXPORT,
            description='Respaldo completo de base de datos exportado.',
            user_id=current_user.id,
            request=request,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()

    ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    filename = f'monetra-backup-{ts}.mntrbak'

    return Response(
        blob,
        status=200,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'application/octet-stream',
            'Content-Length': str(len(blob)),
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache',
        },
    )


# ── Restore ───────────────────────────────────────────────────────────────────

_CONFIRM_WORD = 'RESTAURAR'


@backup_bp.route('/restore', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get('BACKUP_RESTORE_RATE_LIMIT', '5 per hour'), methods=['POST'])
def restore_db():
    _admin_required()

    # 1 — Verify account password (re-authentication)
    account_password = request.form.get('account_password', '')
    if not current_user.check_password(account_password):
        flash('Contraseña de la cuenta incorrecta. La restauración fue cancelada.', 'danger')
        return redirect(url_for('main.configurar'))

    # 2 — Verify confirmation word
    confirm = request.form.get('confirm', '').strip().upper()
    if confirm != _CONFIRM_WORD:
        flash(
            f'Debes escribir exactamente "{_CONFIRM_WORD}" para confirmar la restauración.',
            'danger',
        )
        return redirect(url_for('main.configurar'))

    # 3 — Read and validate uploaded file
    uploaded = request.files.get('backup_file')
    if not uploaded or not uploaded.filename:
        flash('Debes seleccionar un archivo de respaldo.', 'danger')
        return redirect(url_for('main.configurar'))

    backup_password = request.form.get('backup_password', '').strip()
    if not backup_password:
        flash('La contraseña del respaldo no puede estar vacía.', 'danger')
        return redirect(url_for('main.configurar'))

    try:
        blob = uploaded.read()
    except Exception:
        # H3: don't expose internal exception to the UI
        current_app.logger.exception('Failed to read backup upload (user_id=%s)', current_user.id)
        flash('No se pudo leer el archivo. Inténtalo de nuevo.', 'danger')
        return redirect(url_for('main.configurar'))

    # 4 — Decrypt and validate (does NOT touch the DB yet)
    try:
        sql_bytes = read_backup(blob, backup_password)
    except ValueError as exc:
        # ValueError messages from read_backup are intentionally user-safe
        flash(f'El archivo de respaldo no es válido: {exc}', 'danger')
        return redirect(url_for('main.configurar'))
    except Exception:
        # H3: unexpected errors (struct, I/O) must not leak internals
        current_app.logger.exception('Unexpected error processing backup (user_id=%s)', current_user.id)
        flash('No se pudo procesar el archivo de respaldo. Revisa los registros del servidor.', 'danger')
        return redirect(url_for('main.configurar'))

    # 5 — Audit BEFORE restore (committed to current DB; will be overwritten by restore —
    #     acceptable; the event also goes to the app log for durable traceability)
    current_app.logger.warning(
        'DB RESTORE initiated: user_id=%s file=%s ip=%s',
        current_user.id,
        uploaded.filename[:100],
        (request.headers.get('X-Forwarded-For') or request.remote_addr or ''),
    )
    try:
        log_event(
            ev.ADMIN_DB_RESTORE,
            description=f'Restauración de base de datos iniciada (archivo: {uploaded.filename[:100]}).',
            user_id=current_user.id,
            request=request,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()

    # 6 — Safety snapshot: dump current DB before overwriting (H6).
    #     Saved to a temp file so the admin can recover if the restore file was wrong.
    snapshot_path = _save_safety_snapshot()
    if snapshot_path:
        current_app.logger.warning('Pre-restore safety snapshot saved to %s', snapshot_path)
    else:
        current_app.logger.warning(
            'Could not create pre-restore snapshot (user_id=%s) — proceeding without it',
            current_user.id,
        )

    # 7 — Execute the restore (overwrites the entire database)
    try:
        restore_database(sql_bytes)
    except Exception:
        # H3: mysqldump/mysql stderr may contain DB host, user, table names
        current_app.logger.exception('DB restore failed (user_id=%s)', current_user.id)
        flash('La restauración falló. Revisa los registros del servidor.', 'danger')
        return redirect(url_for('main.configurar'))

    # 8 — Invalidate ALL active web sessions (H2).
    #     After restore the users table is replaced; any session cookie signed with
    #     the same SECRET_KEY would still authenticate against the restored DB.
    #     Setting sessions_valid_after = now() forces every user to re-login on
    #     their next request (enforced by the before_request hook in app/__init__.py).
    db.session.expire_all()
    restoring_user_id = current_user.id
    try:
        config = AppConfig.query.first()
        now_utc = datetime.now(timezone.utc)
        if config is None:
            config = AppConfig(allow_registration=True, sessions_valid_after=now_utc)
            db.session.add(config)
        else:
            config.sessions_valid_after = now_utc
        db.session.commit()
    except Exception:
        current_app.logger.exception('Could not set sessions_valid_after after restore')
        db.session.rollback()

    # 9 — Force-logout the admin performing the restore and clear their session
    logout_user()
    session.clear()

    current_app.logger.warning('DB RESTORE completed successfully by user_id=%s', restoring_user_id)
    flash(
        'La base de datos fue restaurada exitosamente. '
        'Todos los usuarios deberán iniciar sesión de nuevo.',
        'success',
    )
    return redirect(url_for('auth.login'))
