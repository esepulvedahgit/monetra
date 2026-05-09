from functools import wraps

from flask import jsonify, request
from flask_login import login_required, current_user

from app import db
from app.demo_data import demo_data_bp
from app.demo_data.service import (
    get_demo_data_summary,
    generate_demo_data,
    reset_demo_data,
)
from app.audit.logger import log_event
from app.audit import events as ev


def _admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'ok': False, 'error': 'Acceso restringido a administradores.'}), 403
        return f(*args, **kwargs)
    return decorated


@demo_data_bp.route('/status', methods=['GET'])
@login_required
@_admin_required
def status():
    summary = get_demo_data_summary(current_user.id)
    has_demo = summary['count'] > 0
    return jsonify({'ok': True, 'has_demo': has_demo, **summary})


@demo_data_bp.route('/load', methods=['POST'])
@login_required
@_admin_required
def load():
    ok, message = generate_demo_data(current_user.id)
    summary = get_demo_data_summary(current_user.id) if ok else {}
    try:
        log_event(ev.ADMIN_DEMO_LOAD, description=message[:200], user_id=current_user.id, request=request)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({'ok': ok, 'message': message, **summary})


@demo_data_bp.route('/reset', methods=['POST'])
@login_required
@_admin_required
def reset():
    count = reset_demo_data(current_user.id)
    try:
        log_event(ev.ADMIN_DEMO_RESET, description=f'{count} registros eliminados', user_id=current_user.id, request=request)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({'ok': True, 'message': f'{count} registros demo eliminados.', 'count': count})
