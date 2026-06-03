from flask import request, jsonify
from flask_login import login_required, current_user
from flask_babel import gettext as _

from app.scanner import scanner_bp
from app.scanner.providers import extract_receipt
from app.models import Category, UserAIConfig  # noqa: F401 — UserAIConfig imported for type clarity


@scanner_bp.route('/scanner/extract', methods=['POST'])
@login_required
def scanner_extract():
    """Extract receipt data from an uploaded image using the user's AI config."""
    # --- Validate AI config ---
    ai_config = getattr(current_user, 'ai_config', None)
    if not ai_config or not ai_config.enabled:
        return jsonify({'error': _('Escáner no configurado. Ve a Configuración → Escáner IA.')}), 400

    # --- Validate image file ---
    image_file = request.files.get('image')
    if not image_file or not image_file.filename:
        return jsonify({'error': _('No se proporcionó una imagen.')}), 400

    mime_type = image_file.mimetype or ''
    if not mime_type.startswith('image/'):
        return jsonify({'error': _('El archivo debe ser una imagen.')}), 400

    image_bytes = image_file.read()
    if not image_bytes:
        return jsonify({'error': _('La imagen está vacía.')}), 400

    # --- Extract receipt data ---
    try:
        result = extract_receipt(ai_config, image_bytes, mime_type)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 422

    # --- Build description from items ---
    items = result.get('items') or []
    parts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        qty = item.get('qty')
        if qty is not None:
            try:
                qty = float(qty)
            except (TypeError, ValueError):
                qty = None
        price = item.get('line_total') or item.get('unit_price')
        if price is not None:
            try:
                price = float(price)
            except (TypeError, ValueError):
                price = None
        part = name
        if qty and qty != 1:
            part += f" x{int(qty)}" if qty == int(qty) else f" x{qty}"
        if price:
            part += f" ${price:.2f}"
        if part:
            parts.append(part)
    description = ', '.join(parts)[:2000]

    # --- Resolve category ---
    resolved_category = None
    category_id_raw = request.form.get('category_id')
    if category_id_raw:
        try:
            category_id = int(category_id_raw)
            resolved_category = Category.query.filter(
                Category.id == category_id,
                (Category.user_id == current_user.id) | (Category.user_id.is_(None))
            ).first()
        except (ValueError, TypeError):
            resolved_category = None

    if resolved_category is None:
        # Fall back to the global "Scanner" category
        resolved_category = Category.query.filter_by(
            name='Scanner',
            user_id=None,
            type='expense',
        ).first()

    if resolved_category is None:
        return jsonify({'error': _('No se encontró la categoría Scanner. Contacte al administrador.')}), 500

    return jsonify({
        'amount': result.get('total'),
        'description': description,
        'merchant': result.get('merchant'),
        'date': result.get('date'),
        'currency': result.get('currency'),
        'category_id': resolved_category.id if resolved_category else None,
        'category_name': resolved_category.name if resolved_category else None,
    })
