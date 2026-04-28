from flask import Blueprint

demo_data_bp = Blueprint('demo_data', __name__, url_prefix='/admin/demo')

from app.demo_data import routes  # noqa: F401, E402
