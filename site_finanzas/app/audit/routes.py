from flask import render_template, request, abort
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models import AuditLog, User
from app.audit.events import CATEGORY_META, category_of
from . import audit_bp

_PAGE_SIZE = 50


@audit_bp.route('/')
@login_required
def index():
    if not current_user.is_admin:
        abort(403)

    # ── filters ──────────────────────────────────────────────────────────────
    category  = request.args.get('category', '').strip()
    ip_filter = request.args.get('ip', '').strip()
    user_filter = request.args.get('user_id', '').strip()
    page = max(1, request.args.get('page', 1, type=int))

    query = AuditLog.query.order_by(AuditLog.created_at.desc())

    if category and category in CATEGORY_META:
        query = query.filter(AuditLog.event_type.like(f'{category}.%'))
    if ip_filter:
        query = query.filter(AuditLog.ip_address.like(f'%{ip_filter}%'))
    if user_filter and user_filter.isdigit():
        query = query.filter(AuditLog.user_id == int(user_filter))

    pagination = query.paginate(page=page, per_page=_PAGE_SIZE, error_out=False)
    logs = pagination.items

    # ── KPI counts ───────────────────────────────────────────────────────────
    total_events = AuditLog.query.count()

    # Count per category prefix (Python-side grouping on a lightweight aggregate)
    cat_rows = db.session.query(AuditLog.event_type, func.count(AuditLog.id)).group_by(AuditLog.event_type).all()
    cat_counts: dict[str, int] = {}
    for evt, cnt in cat_rows:
        cat_counts[category_of(evt)] = cat_counts.get(category_of(evt), 0) + cnt

    # Unique IPs and unique users in the last 7 days
    from datetime import datetime, timezone, timedelta
    since_7d = datetime.now(timezone.utc) - timedelta(days=7)
    unique_ips = db.session.query(func.count(func.distinct(AuditLog.ip_address))).filter(
        AuditLog.created_at >= since_7d).scalar() or 0
    unique_users = db.session.query(func.count(func.distinct(AuditLog.user_id))).filter(
        AuditLog.created_at >= since_7d, AuditLog.user_id.isnot(None)).scalar() or 0

    # ── Chart data (donut) ───────────────────────────────────────────────────
    chart_labels  = [meta['label'] for meta in CATEGORY_META.values()]
    chart_data    = [cat_counts.get(k, 0) for k in CATEGORY_META]
    chart_colors  = [meta['color'] for meta in CATEGORY_META.values()]
    chart_borders = [meta['border'] for meta in CATEGORY_META.values()]

    # ── User map for display ─────────────────────────────────────────────────
    user_ids = {log.user_id for log in logs if log.user_id}
    users_map = {}
    if user_ids:
        for u in User.query.filter(User.id.in_(user_ids)).all():
            users_map[u.id] = u.username

    return render_template(
        'admin/audit.html',
        logs=logs,
        pagination=pagination,
        total_events=total_events,
        cat_counts=cat_counts,
        unique_ips=unique_ips,
        unique_users=unique_users,
        chart_labels=chart_labels,
        chart_data=chart_data,
        chart_colors=chart_colors,
        chart_borders=chart_borders,
        category_meta=CATEGORY_META,
        users_map=users_map,
        filter_category=category,
        filter_ip=ip_filter,
        filter_user=user_filter,
        page_size=_PAGE_SIZE,
    )
