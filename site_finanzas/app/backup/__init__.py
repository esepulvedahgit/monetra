from flask import Blueprint

backup_bp = Blueprint('backup', __name__, url_prefix='/admin/backup')

from app.backup import routes  # noqa: F401, E402
