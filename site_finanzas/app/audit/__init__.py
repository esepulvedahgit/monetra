from flask import Blueprint

audit_bp = Blueprint('audit', __name__, url_prefix='/admin/audit')

from . import routes  # noqa: E402, F401
