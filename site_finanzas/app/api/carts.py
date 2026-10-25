"""API de Mi Carrito (/api/v1/carts) para la app móvil.

Mismas reglas que el bot y la web (app/cart/service.py). El escaneo de una
etiqueta de precio *sugiere* el producto para que el cliente lo confirme creando
el ítem, o con ``?add=1`` lo agrega de inmediato (verificación automática, como el
modo automático del bot). La imagen se procesa en memoria y nunca se guarda.
"""
from datetime import date as date_type
from decimal import Decimal, InvalidOperation

from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db, limiter
from app.api import api_v1
from app.api.decorators import api_login_required, get_current_api_user
from app.api.schemas import cart_item_schema, cart_schema, transaction_schema
from app.audit.events import CART_FINALIZE, CART_MOVEMENT
from app.audit.logger import log_event
from app.cart import service as svc
from app.models import Cart, CartItem

_MAX_PER_PAGE = 100
_MAX_KEY_LEN = 128

_ERRORS = {
    'invalid_amount': (400, 'Monto inválido'),
    'invalid_category': (400, 'Categoría no encontrada o no es de gasto'),
    'cart_closed': (409, 'El carrito ya fue finalizado'),
    'cart_empty': (409, 'El carrito no tiene productos'),
    'cart_full': (409, 'El carrito alcanzó el máximo de productos'),
    'cart_not_finalized': (409, 'Finaliza el carrito antes de registrar el movimiento'),
    'already_registered': (409, 'El carrito ya tiene un movimiento registrado'),
    'store_name_required': (400, 'store_name es obligatorio para crear un carrito'),
}


def _error(message, code='validation_error', status=400):
    return jsonify({'error': message, 'code': code, 'message': message}), status


def _cart_error(exc: svc.CartError):
    status, message = _ERRORS.get(exc.code, (400, 'Operación inválida'))
    return _error(message, exc.code, status)


def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() else None


def _positive_int(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 and str(number) == str(value).strip() else None


def _cart_or_404(user, cart_id):
    cart = svc.get_user_cart(user.id, cart_id)
    if cart is None:
        return None, _error('Carrito no encontrado', 'not_found', 404)
    return cart, None


def _detail(cart, status=200):
    return jsonify(cart_schema(cart, include_items=True, movement=svc.linked_transaction(cart))), status


def _movement_kwargs(data):
    """Lee category_id/amount/date/description opcionales. Devuelve (kwargs, error)."""
    kwargs = {}
    if data.get('category_id') is not None:
        category_id = _positive_int(data['category_id'])
        if category_id is None:
            return None, _error('Categoría inválida')
        kwargs['category_id'] = category_id
    if data.get('amount') is not None:
        amount = _decimal(data['amount'])
        if amount is None:
            return None, _error('Monto inválido')
        kwargs['amount'] = amount
    if data.get('date') is not None:
        try:
            kwargs['tx_date'] = date_type.fromisoformat(data['date'])
        except (TypeError, ValueError):
            return None, _error('Fecha inválida (use YYYY-MM-DD)')
    if data.get('description') is not None:
        if not isinstance(data['description'], str) or len(data['description']) > 500:
            return None, _error('Descripción inválida')
        kwargs['description'] = data['description']
    return kwargs, None


# ── Consulta ──────────────────────────────────────────────────────────────────

@api_v1.get('/carts')
@api_login_required
def list_carts():
    user = get_current_api_user()
    status = request.args.get('status')
    if status not in (None, 'open', 'finalized'):
        return _error("status debe ser 'open' o 'finalized'")
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if page < 1 or not 1 <= per_page <= _MAX_PER_PAGE:
        return _error('Paginación inválida')

    query = Cart.query.filter_by(user_id=user.id)
    if status:
        query = query.filter_by(status=status)
    pagination = (query
                  .order_by(Cart.finalized_at.is_(None).desc(), Cart.finalized_at.desc(), Cart.id.desc())
                  .paginate(page=page, per_page=per_page, error_out=False))
    return jsonify({
        'carts': [cart_schema(c) for c in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
        'has_next': pagination.has_next,
    }), 200


@api_v1.get('/carts/current')
@api_login_required
def current_cart():
    """Carrito abierto del usuario, o ``{"cart": null}``. Cierra antes uno inactivo."""
    user = get_current_api_user()
    svc.close_stale_cart(user.id)
    db.session.commit()
    cart = svc.get_open_cart(user.id)
    if cart is None:
        return jsonify({'cart': None}), 200
    return jsonify({'cart': cart_schema(cart, include_items=True)}), 200


@api_v1.get('/carts/<int:cart_id>')
@api_login_required
def get_cart(cart_id):
    cart, error = _cart_or_404(get_current_api_user(), cart_id)
    if error:
        return error
    return _detail(cart)


@api_v1.get('/carts/compare')
@api_login_required
def compare_carts():
    user = get_current_api_user()
    a, error = _cart_or_404(user, request.args.get('a', type=int) or 0)
    if error:
        return error
    b, error = _cart_or_404(user, request.args.get('b', type=int) or 0)
    if error:
        return error
    result = svc.compare_carts(a, b)

    def _side(entry):
        if entry is None:
            return None
        return {'unit_price': float(entry['unit_price']), 'qty': float(entry['qty']),
                'line_total': float(entry['line_total'])}

    return jsonify({
        'before': cart_schema(result['before']),
        'after': cart_schema(result['after']),
        'total_diff': float(result['total_diff']),
        'items': [{
            'name': r['name'],
            'before': _side(r['old']),
            'after': _side(r['new']),
            'unit_price_diff': float(r['diff']) if r['diff'] is not None else None,
            'unit_price_pct': round(r['pct'], 2) if r['pct'] is not None else None,
        } for r in result['rows']],
    }), 200


# ── Carrito ───────────────────────────────────────────────────────────────────

@api_v1.post('/carts')
@api_login_required
def start_cart():
    """Inicia un carrito en ``store_name`` (obligatorio).

    Si ya hay uno abierto lo devuelve (200) en vez de crear otro (201).
    """
    user = get_current_api_user()
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return _error('Se requiere un objeto JSON')

    svc.close_stale_cart(user.id)
    existing = svc.get_open_cart(user.id)
    if existing is not None:
        db.session.commit()
        return _detail(existing)
    try:
        cart = svc.start_cart(user.id, data.get('store_name'), source='api')
    except svc.CartError as exc:
        db.session.rollback()
        return _cart_error(exc)
    db.session.commit()
    return _detail(cart, 201)


@api_v1.patch('/carts/<int:cart_id>')
@api_login_required
def update_cart(cart_id):
    cart, error = _cart_or_404(get_current_api_user(), cart_id)
    if error:
        return error
    data = _json_body()
    if data is None:
        return _error('Se requiere JSON')
    if 'store_name' in data:
        try:
            svc.rename_store(cart, data['store_name'])
        except svc.CartError as exc:
            db.session.rollback()
            return _cart_error(exc)
    db.session.commit()
    return _detail(cart)


@api_v1.delete('/carts/<int:cart_id>')
@api_login_required
def delete_cart(cart_id):
    cart, error = _cart_or_404(get_current_api_user(), cart_id)
    if error:
        return error
    svc.discard(cart)
    db.session.commit()
    return jsonify({'message': 'Eliminado'}), 200


# ── Productos ─────────────────────────────────────────────────────────────────

@api_v1.post('/carts/<int:cart_id>/items')
@api_login_required
def add_cart_item(cart_id):
    """Agrega un producto.

    Body: ``{"name", "qty"?, "unit_price"}`` o ``{"name", "qty"?, "line_total"}`` (uno de los dos).
    Acepta ``Idempotency-Key`` para que un reintento devuelva el mismo ítem.
    """
    user = get_current_api_user()
    cart, error = _cart_or_404(user, cart_id)
    if error:
        return error
    data = _json_body()
    if data is None:
        return _error('Se requiere JSON')

    key, error = _idempotency_key()
    if error:
        return error
    replay = _replayed_item(cart, key)
    if replay:
        return replay

    name = data.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        return _error('Nombre de producto inválido')
    qty = _decimal(data.get('qty', 1))
    if qty is None:
        return _error('Cantidad inválida')
    has_unit, has_line = 'unit_price' in data, 'line_total' in data
    if has_unit == has_line:
        return _error('Envía unit_price o line_total (solo uno)')
    price = _decimal(data['unit_price'] if has_unit else data['line_total'])
    if price is None:
        return _error('Monto inválido')
    line_total = price * qty if has_unit else price
    return _add_locked(cart, key, name=name, line_total=line_total, qty=qty, source='api')


def _idempotency_key():
    key = request.headers.get('Idempotency-Key', '').strip()
    if len(key) > _MAX_KEY_LEN:
        return None, _error('Idempotency-Key inválido')
    return key or None, None


def _replayed_item(cart, key, **extra):
    """Respuesta del ítem ya creado con ``key`` (reintento del cliente), o None."""
    if not key:
        return None
    previous = CartItem.query.filter_by(cart_id=cart.id, client_request_id=key).first()
    if previous is None:
        return None
    return jsonify({'item': cart_item_schema(previous), 'cart': cart_schema(cart), **extra}), 200


def _add_locked(cart, key, *, name, line_total, qty, source, **extra):
    """Agrega el ítem con el carrito bloqueado, para que envíos simultáneos no desfasen el total."""
    svc.lock_cart(cart)
    replay = _replayed_item(cart, key, **extra)
    if replay:
        db.session.commit()
        return replay
    try:
        item = svc.add_item(cart, name, line_total, qty=qty, source=source, client_request_id=key)
        db.session.commit()
    except svc.CartError as exc:
        db.session.rollback()
        return _cart_error(exc)
    except IntegrityError:
        # Dos reintentos simultáneos con la misma clave: devolver el que ganó.
        db.session.rollback()
        replay = _replayed_item(cart, key, **extra)
        if replay:
            return replay
        raise
    return jsonify({'item': cart_item_schema(item), 'cart': cart_schema(cart), **extra}), 201


@api_v1.delete('/carts/<int:cart_id>/items/<int:item_id>')
@api_login_required
def delete_cart_item(cart_id, item_id):
    cart, error = _cart_or_404(get_current_api_user(), cart_id)
    if error:
        return error
    svc.lock_cart(cart)
    item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first()
    if item is None:
        db.session.commit()
        return _error('Producto no encontrado', 'not_found', 404)
    try:
        svc.remove_item(cart, item)
        db.session.commit()
    except svc.CartError as exc:
        db.session.rollback()
        return _cart_error(exc)
    return jsonify({'cart': cart_schema(cart)}), 200


@api_v1.post('/carts/<int:cart_id>/scan')
@api_login_required
@limiter.limit(lambda: current_app.config.get('CART_SCAN_RATE_LIMIT', '20 per minute'))
def scan_price_tag(cart_id):
    """Lee la foto de una etiqueta (multipart, campo ``image``) y sugiere nombre y precio.

    Sin ``add`` no agrega nada: el cliente muestra la sugerencia y la confirma con
    POST /items. Con ``?add=1`` agrega el producto al precio normal (la oferta solo
    se informa) y responde como POST /items más la lectura en ``scan``; acepta
    ``Idempotency-Key`` y un reintento no vuelve a consumir la IA.
    """
    from app.email_service import consume_shared_ai_quota, resolve_ai_config
    from app.telegram.image_utils import validate_and_normalize_image
    from app.telegram.providers import extract_price_tag

    user = get_current_api_user()
    cart, error = _cart_or_404(user, cart_id)
    if error:
        return error
    if cart.status != 'open':
        return _cart_error(svc.CartError('cart_closed'))
    add = request.args.get('add') in ('1', 'true')
    key, error = _idempotency_key() if add else (None, None)
    if error:
        return error
    replay = _replayed_item(cart, key, scan=None)
    if replay:
        return replay

    upload = request.files.get('image')
    if upload is None:
        return _error("Se requiere la imagen en el campo 'image'")

    ai_config = resolve_ai_config(user)
    if ai_config is None:
        return _error('El escáner IA no está configurado', 'ai_not_configured', 403)
    # Misma regla que el bot: solo la clave compartida del admin consume cuota diaria.
    if getattr(ai_config, 'user_id', None) != user.id and not consume_shared_ai_quota(user):
        return _error('Límite diario de escaneos alcanzado', 'ai_quota_exceeded', 429)

    try:
        image_bytes, mime_type = validate_and_normalize_image(upload.read())
    except ValueError:
        return _error('Imagen inválida', 'invalid_image')

    try:
        result = extract_price_tag(ai_config, image_bytes, mime_type)
    except ValueError:
        return _error('No se encontró un precio en la imagen', 'price_not_found', 422)

    price = _decimal(result.get('price'))
    offer = _decimal(result.get('offer_price'))
    if (price is None or price <= 0) and offer is not None and offer > 0:
        price, offer = offer, None
    if price is None or price <= 0 or price > svc.MAX_AMOUNT:
        return _error('No se encontró un precio en la imagen', 'price_not_found', 422)
    if offer is not None and not 0 < offer < price:
        offer = None

    unit = (result.get('unit') or 'unit').lower()
    name = result.get('name')
    name = name.strip()[:200] if isinstance(name, str) and name.strip() else None
    scan = {
        'name': name,
        'price': float(price.quantize(Decimal('0.01'))),
        'offer_price': float(offer.quantize(Decimal('0.01'))) if offer is not None else None,
        'offer_text': result.get('offer_text') if offer is not None else None,
        'unit': 'kg' if unit == 'kg' else 'unit',
    }
    if not add:
        return jsonify(scan), 200
    return _add_locked(cart, key, name=name or 'Producto', line_total=price.quantize(Decimal('0.01')),
                       qty=1, source='photo', scan=scan)


# ── Finalizar y movimiento ────────────────────────────────────────────────────

@api_v1.post('/carts/<int:cart_id>/finalize')
@api_login_required
def finalize_cart(cart_id):
    """Cierra el carrito. ``{"register_movement": true, ...}`` además crea el gasto.

    Con ``register_movement`` acepta ``category_id``, ``amount`` (monto pagado en caja),
    ``date`` y ``description`` opcionales.
    """
    user = get_current_api_user()
    cart, error = _cart_or_404(user, cart_id)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return _error('Se requiere un objeto JSON')
    register = data.get('register_movement', False)
    if not isinstance(register, bool):
        return _error('register_movement debe ser booleano')
    kwargs, error = _movement_kwargs(data) if register else ({}, None)
    if error:
        return error

    try:
        tx = svc.finalize(cart, register=register, **kwargs)
        log_event(CART_FINALIZE, user_id=user.id,
                  description=f"cart={cart.id} total={cart.total} items={cart.item_count}", request=request)
        if tx is not None:
            log_event(CART_MOVEMENT, user_id=user.id, description=f"cart={cart.id} amount={tx.amount}",
                      request=request)
        db.session.commit()
    except svc.CartError as exc:
        db.session.rollback()
        return _cart_error(exc)
    return _detail(cart)


@api_v1.post('/carts/<int:cart_id>/movement')
@api_login_required
def register_cart_movement(cart_id):
    """Registra después el movimiento de un carrito guardado con "solo guardar"."""
    user = get_current_api_user()
    cart, error = _cart_or_404(user, cart_id)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return _error('Se requiere un objeto JSON')
    kwargs, error = _movement_kwargs(data)
    if error:
        return error
    try:
        tx = svc.register_movement(cart, **kwargs)
        log_event(CART_MOVEMENT, user_id=user.id, description=f"cart={cart.id} amount={tx.amount}",
                  request=request)
        db.session.commit()
    except svc.CartError as exc:
        db.session.rollback()
        return _cart_error(exc)
    return jsonify({'movement': transaction_schema(tx), 'cart': cart_schema(cart)}), 201
