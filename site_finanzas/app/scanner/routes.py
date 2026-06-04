import io

from flask import current_app, request, jsonify
from flask_login import login_required, current_user
from flask_babel import gettext as _

from app import limiter
from app.scanner import scanner_bp
from app.scanner.providers import extract_receipt, test_connection
from app.models import Category, UserAIConfig  # noqa: F401 — UserAIConfig imported for type clarity
from app.email_service import decrypt_ai_token

# ---------------------------------------------------------------------------
# Allowed image magic-byte signatures
# ---------------------------------------------------------------------------
_MAGIC = {
    b'\xff\xd8\xff':                   'image/jpeg',
    b'\x89PNG\r\n\x1a\n':             'image/png',
    # WebP: 'RIFF????WEBP' — validated separately below
    # HEIC/HEIF: ISO Base Media File Format — 'ftyp' box at offset 4
}
_ALLOWED_MIMES = frozenset({
    'image/jpeg', 'image/png', 'image/webp',
    'image/heic', 'image/heif',
})


def _detect_mime(header: bytes) -> str | None:
    """Return MIME type from first 12 bytes, or None if unrecognised."""
    if header[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp'
    if len(header) >= 12 and header[4:8] == b'ftyp':
        return 'image/heic'
    return None


def _validate_and_normalize_image(image_file):
    """Read, validate by magic bytes, convert HEIC→JPEG if needed.

    Returns (image_bytes: bytes, mime_type: str).
    Raises ValueError with a human-readable message on invalid input.
    The uploaded filename is intentionally ignored.
    """
    raw = image_file.read()
    if not raw:
        raise ValueError(_('La imagen está vacía.'))

    header = raw[:12]
    detected = _detect_mime(header)

    if detected is None:
        raise ValueError(_(
            'Formato no compatible. Usa PNG, JPG, WEBP o HEIC.'
        ))

    # Normalise all formats to JPEG before sending to AI providers.
    # PNG screenshots can be 3-7 MB; JPEG at 88% quality is ~200-500 KB,
    # which avoids payload-size failures and timeouts on provider APIs.
    try:
        from PIL import Image

        if detected in ('image/heic', 'image/heif'):
            import pillow_heif
            heif_file = pillow_heif.open_heif(raw)
            pil_img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, 'raw')
        else:
            pil_img = Image.open(io.BytesIO(raw))

        # Convert palette/transparency modes that JPEG cannot encode
        if pil_img.mode in ('RGBA', 'LA', 'P'):
            pil_img = pil_img.convert('RGB')
        elif pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')

        buf = io.BytesIO()
        pil_img.save(buf, format='JPEG', quality=92, optimize=True)
        return buf.getvalue(), 'image/jpeg'

    except Exception:
        if detected in ('image/heic', 'image/heif'):
            raise ValueError(_('No se pudo procesar el archivo HEIC. Asegúrate de que no esté dañado.'))
        # Fallback: send raw bytes with detected MIME (JPEG already correct)
        return raw, detected


@scanner_bp.route('/scanner/test', methods=['POST'], endpoint='test')
@login_required
def scanner_test():
    """Test AI provider connection with a lightweight text-only call."""
    provider = (request.form.get('provider') or '').strip()
    model = (request.form.get('model') or '').strip()
    base_url = (request.form.get('base_url') or '').strip()
    api_token_raw = (request.form.get('api_token') or '').strip()

    if not provider:
        return jsonify({'ok': False, 'message': _('Selecciona un proveedor.')}), 200

    # Use submitted token if provided, otherwise fall back to stored encrypted token
    if api_token_raw:
        token = api_token_raw
    else:
        ai_config = getattr(current_user, 'ai_config', None)
        token = decrypt_ai_token(ai_config.api_token_encrypted) if (ai_config and ai_config.api_token_encrypted) else ''

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
    # --- Validate AI config ---
    ai_config = getattr(current_user, 'ai_config', None)
    if not ai_config or not ai_config.enabled:
        return jsonify({'error': _('Escáner no configurado. Ve a Configuración → Escáner IA.')}), 400

    # --- Validate and normalise uploaded file ---
    image_file = request.files.get('image')
    if not image_file:
        return jsonify({'error': _('No se proporcionó una imagen.')}), 400

    try:
        image_bytes, mime_type = _validate_and_normalize_image(image_file)
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
