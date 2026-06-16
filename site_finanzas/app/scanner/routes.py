from flask import current_app, request, jsonify
from flask_login import login_required, current_user
from flask_babel import gettext as _

from app import limiter
from app.scanner import scanner_bp
from app.scanner.image_utils import validate_and_normalize_image
from app.scanner.providers import extract_receipt, test_connection
from app.models import Category, UserAIConfig  # noqa: F401 — UserAIConfig imported for type clarity
from app.email_service import decrypt_ai_token, resolve_ai_config


@scanner_bp.route('/scanner/test', methods=['POST'], endpoint='test')
@limiter.limit("10 per minute", methods=['POST'])
@login_required
def scanner_test():
    """Test AI provider connection with a lightweight text-only call."""
    provider = (request.form.get('provider') or '').strip()
    model = (request.form.get('model') or '').strip()
    base_url = (request.form.get('base_url') or '').strip()
    api_token_raw = (request.form.get('api_token') or '').strip()

    if not provider:
        return jsonify({'ok': False, 'message': _('Selecciona un proveedor.')}), 200

    ai_config = getattr(current_user, 'ai_config', None)
    has_saved = bool(ai_config and ai_config.api_token_encrypted)

    if has_saved:
        # Always use the stored token — never accept a raw token from the form
        # when one is already saved. Prevents using this endpoint as an oracle
        # to validate third-party API keys.
        token = decrypt_ai_token(ai_config.api_token_encrypted)
    elif api_token_raw:
        # First-time setup: no saved token yet, accept the field value
        token = api_token_raw
    else:
        token = ''

    try:
        test_connection(provider, model, base_url, token)
    except ValueError as exc:
        return jsonify({'ok': False, 'message': str(exc)}), 200

    return jsonify({'ok': True, 'message': _('Conexión válida. Token y modelo correctos.')}), 200


@scanner_bp.route('/scanner/extract', methods=['POST'], endpoint='extract')
@limiter.limit("30 per minute", methods=['POST'])
@login_required
def scanner_extract():
    """Extract receipt data from an uploaded image using the user's AI config."""
    # --- Validate AI config (propia o del admin compartida) ---
    ai_config = resolve_ai_config(current_user)
    if not ai_config:
        return jsonify({'error': _('Escáner no configurado. Ve a Configuración → Escáner IA.')}), 400

    # --- Validate and normalise uploaded file ---
    image_file = request.files.get('image')
    if not image_file:
        return jsonify({'error': _('No se proporcionó una imagen.')}), 400

    try:
        image_bytes, mime_type = validate_and_normalize_image(image_file)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    # --- Extract receipt data ---
    try:
        result = extract_receipt(ai_config, image_bytes, mime_type)
    except ValueError as exc:
        current_app.logger.warning("Scanner extract error: %s", exc)
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
