"""Authenticated web distribution and first-admin publication of Android APKs."""
from __future__ import annotations

import os
from pathlib import Path

from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app import db
from app.audit import events as ev
from app.audit.logger import log_event
from app.mobile_releases import mobile_releases_bp
from app.mobile_releases.service import ReleaseValidationError, current_apk_path, stage_apk
from app.models import MobileRelease


def _admin_required():
    if not (current_user.is_authenticated and current_user.is_admin and current_user.is_first_admin):
        abort(403)


def _active_user_required():
    if not current_user.is_authenticated:
        abort(401)
    if current_user.is_suspended:
        abort(403)


def _current_release():
    return MobileRelease.query.filter_by(is_current=True).order_by(MobileRelease.id.desc()).first()


@mobile_releases_bp.route('/mobile')
@login_required
def index():
    _active_user_required()
    return render_template('mobile_releases/index.html', release=_current_release(), title='Aplicación Android')


@mobile_releases_bp.route('/mobile/download')
@login_required
def download():
    _active_user_required()
    release = _current_release()
    apk_path = current_apk_path(current_app.config['MOBILE_RELEASES_DIR'])
    if release is None or not apk_path.is_file():
        abort(404)

    try:
        log_event(ev.MOBILE_RELEASE_DOWNLOADED,
                  description=f'version={release.version} code={release.version_code}',
                  user_id=current_user.id, request=request)
        db.session.commit()
    except Exception:
        db.session.rollback()

    response = send_file(
        apk_path,
        mimetype='application/vnd.android.package-archive',
        as_attachment=True,
        download_name=f'monetra-{release.version}.apk',
        conditional=True,
        max_age=0,
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'private, no-store, max-age=0'
    return response


@mobile_releases_bp.route('/admin/mobile')
@login_required
def admin_index():
    _admin_required()
    releases = MobileRelease.query.order_by(MobileRelease.published_at.desc()).all()
    return render_template('mobile_releases/admin.html', releases=releases,
                           current_release=_current_release(), title='Aplicación Android')


@mobile_releases_bp.route('/admin/mobile/publish', methods=['POST'])
@login_required
def publish():
    _admin_required()
    if not current_user.check_password(request.form.get('account_password', '')):
        flash('Contraseña de la cuenta incorrecta. La publicación fue cancelada.', 'danger')
        return redirect(url_for('mobile_releases.admin_index'))

    version = request.form.get('version', '').strip()
    notes = request.form.get('notes', '').strip()
    version_code_raw = request.form.get('version_code', '').strip()
    if not version or len(version) > 40:
        flash('La versión es obligatoria y no puede superar 40 caracteres.', 'danger')
        return redirect(url_for('mobile_releases.admin_index'))
    if len(notes) > 2000:
        flash('Las notas de versión no pueden superar 2000 caracteres.', 'danger')
        return redirect(url_for('mobile_releases.admin_index'))
    try:
        version_code = int(version_code_raw)
    except ValueError:
        flash('El código de versión debe ser un número entero.', 'danger')
        return redirect(url_for('mobile_releases.admin_index'))
    latest_code = db.session.query(db.func.max(MobileRelease.version_code)).scalar()
    if version_code < 1 or (latest_code is not None and version_code <= latest_code):
        flash('El código de versión debe ser mayor al de la publicación actual.', 'danger')
        return redirect(url_for('mobile_releases.admin_index'))

    upload = request.files.get('apk_file')
    if upload is None or not upload.filename:
        flash('Debes seleccionar un archivo APK.', 'danger')
        return redirect(url_for('mobile_releases.admin_index'))

    try:
        staged, checksum, size, certificate = stage_apk(
            upload,
            current_app.config['MOBILE_RELEASES_DIR'],
            current_app.config['MAX_MOBILE_APK_BYTES'],
            current_app.config['MOBILE_APK_SIGNER_SHA256'],
        )
    except ReleaseValidationError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('mobile_releases.admin_index'))
    except Exception:
        current_app.logger.exception('Android APK staging failed (user_id=%s)', current_user.id)
        flash('No se pudo validar el APK. Inténtalo nuevamente.', 'danger')
        return redirect(url_for('mobile_releases.admin_index'))

    try:
        MobileRelease.query.filter_by(is_current=True).update({'is_current': False})
        release = MobileRelease(
            version=version,
            version_code=version_code,
            notes=notes or None,
            size_bytes=size,
            sha256=checksum,
            certificate_sha256=certificate,
            is_current=True,
            published_by_id=current_user.id,
        )
        db.session.add(release)
        db.session.flush()
        # os.replace is atomic on the persistent volume.  Old APK bytes are not retained.
        os.replace(staged, current_apk_path(current_app.config['MOBILE_RELEASES_DIR']))
        log_event(ev.MOBILE_RELEASE_PUBLISHED,
                  description=f'version={version} code={version_code} sha256={checksum}',
                  user_id=current_user.id, request=request)
        db.session.commit()
    except Exception:
        db.session.rollback()
        Path(staged).unlink(missing_ok=True)
        current_app.logger.exception('Android APK publication failed (user_id=%s)', current_user.id)
        flash('No se pudo publicar el APK. Inténtalo nuevamente.', 'danger')
        return redirect(url_for('mobile_releases.admin_index'))

    flash('La aplicación Android fue publicada correctamente.', 'success')
    return redirect(url_for('mobile_releases.admin_index'))
