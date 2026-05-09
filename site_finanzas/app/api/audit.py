from datetime import datetime

from flask import jsonify, request

from app.api import api_v1
from app.api.decorators import api_login_required, get_current_api_user
from app.api.schemas import audit_log_schema
from app.audit.events import CATEGORY_META
from app.models import AuditLog

_MAX_PER_PAGE = 100


@api_v1.route('/audit/logs', methods=['GET'])
@api_login_required
def get_audit_logs():
    user = get_current_api_user()
    if user.role != 'admin':
        return jsonify({'error': 'Acceso restringido a administradores.'}), 403

    category   = request.args.get('category', '').strip()
    event_type = request.args.get('event_type', '').strip()
    ip         = request.args.get('ip', '').strip()
    since_str  = request.args.get('since', '').strip()
    until_str  = request.args.get('until', '').strip()

    try:
        user_id_filter = int(request.args.get('user_id', '')) if request.args.get('user_id') else None
    except ValueError:
        return jsonify({'error': 'user_id debe ser un entero.'}), 400

    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1

    try:
        per_page = min(_MAX_PER_PAGE, max(1, int(request.args.get('per_page', 50))))
    except ValueError:
        per_page = 50

    query = AuditLog.query.order_by(AuditLog.created_at.desc())

    if category and category in CATEGORY_META:
        query = query.filter(AuditLog.event_type.like(f'{category}.%'))
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if user_id_filter is not None:
        query = query.filter(AuditLog.user_id == user_id_filter)
    if ip:
        query = query.filter(AuditLog.ip_address.like(f'%{ip}%'))

    if since_str:
        try:
            since_dt = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
            query = query.filter(AuditLog.created_at > since_dt)
        except ValueError:
            return jsonify({'error': "El parámetro 'since' debe ser ISO 8601 (ej. 2026-05-04T10:00:00Z)."}), 400

    if until_str:
        try:
            until_dt = datetime.fromisoformat(until_str.replace('Z', '+00:00'))
            query = query.filter(AuditLog.created_at <= until_dt)
        except ValueError:
            return jsonify({'error': "El parámetro 'until' debe ser ISO 8601."}), 400

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'logs':     [audit_log_schema(log) for log in pagination.items],
        'total':    pagination.total,
        'page':     pagination.page,
        'pages':    pagination.pages,
        'per_page': per_page,
    })
