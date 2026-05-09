from app import db
from app.models import AuditLog


def log_event(event_type: str, description: str = None, user_id: int = None, request=None):
    """Append an audit entry to the current DB session. Caller is responsible for commit.

    Safe to call inside error handlers — catches and silently swallows any exception
    so that audit failures never mask the original error.
    """
    try:
        ip = None
        if request is not None:
            ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or '')[:45]
        db.session.add(AuditLog(
            user_id=user_id,
            event_type=event_type,
            description=description,
            ip_address=ip or None,
        ))
    except Exception:
        pass
