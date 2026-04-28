from flask import jsonify
from flask_login import login_required, current_user

from app.demo_data import demo_data_bp
from app.demo_data.service import (
    get_demo_data_summary,
    generate_demo_data,
    reset_demo_data,
)


@demo_data_bp.route('/status', methods=['GET'])
@login_required
def status():
    summary = get_demo_data_summary(current_user.id)
    return jsonify({'ok': True, 'has_demo': summary['count'] > 0, **summary})


@demo_data_bp.route('/load', methods=['POST'])
@login_required
def load():
    ok, message = generate_demo_data(current_user.id)
    summary = get_demo_data_summary(current_user.id) if ok else {}
    return jsonify({'ok': ok, 'message': message, **summary})


@demo_data_bp.route('/reset', methods=['POST'])
@login_required
def reset():
    count = reset_demo_data(current_user.id)
    return jsonify({'ok': True, 'message': f'{count} registros demo eliminados.', 'count': count})
