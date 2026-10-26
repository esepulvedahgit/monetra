"""Lógica de negocio de Mi Carrito.

Compartida por el bot de Telegram, la vista web y (más adelante) la API, para que
las reglas — un solo carrito abierto por usuario, recálculo del total, registro
del movimiento — vivan en un único lugar. Las funciones no hacen commit: el
llamador decide cuándo confirmar la transacción de BD.
"""
import unicodedata
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import current_app

from app import db
from app.models import Cart, CartItem, Category, Transaction

MAX_ITEMS_PER_CART = 300
MAX_AMOUNT = Decimal('9999999999.99')   # máximo para Numeric(12,2)
MAX_QTY = Decimal(9999)
STORE_NAME_MAX = 120
_CENT = Decimal('0.01')

# Categorías de gasto candidatas para el movimiento de un carrito, en orden de preferencia.
_DEFAULT_CATEGORY_NAMES = ('Supermercado', 'Alimentación', 'Telegram')


class CartError(ValueError):
    """Error de negocio del carrito. ``code`` es estable para traducir o mapear a HTTP."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_decimal(value, *, max_value: Decimal = MAX_AMOUNT) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise CartError('invalid_amount') from None
    if not amount.is_finite() or amount <= 0 or amount > max_value:
        raise CartError('invalid_amount')
    return amount


# ── Consulta ──────────────────────────────────────────────────────────────────

def get_open_cart(user_id: int) -> Cart | None:
    return (Cart.query
            .filter_by(user_id=user_id, status='open')
            .order_by(Cart.id.desc())
            .first())


def get_user_cart(user_id: int, cart_id: int) -> Cart | None:
    return Cart.query.filter_by(id=cart_id, user_id=user_id).first()


def is_stale(cart: Cart) -> bool:
    """True si el carrito abierto lleva más de CART_IDLE_HOURS sin actividad."""
    hours = current_app.config.get('CART_IDLE_HOURS', 6)
    updated_at = _aware(cart.updated_at or cart.started_at)
    if updated_at is None:
        return False
    return _now() - updated_at > timedelta(hours=hours)


def close_stale_cart(user_id: int) -> Cart | None:
    """Cierra el carrito abierto si quedó inactivo.

    Un carrito con productos se guarda (sin movimiento) para no perder datos; uno
    vacío se elimina. Devuelve el carrito guardado, o None si no había nada que cerrar
    o el carrito estaba vacío.
    """
    cart = get_open_cart(user_id)
    if cart is None or not is_stale(cart):
        return None
    if not cart.items:
        db.session.delete(cart)
        return None
    cart.status = 'finalized'
    cart.finalized_at = _now()
    return cart


def linked_transaction(cart: Cart) -> Transaction | None:
    """Movimiento asociado, o None si nunca se registró o fue eliminado."""
    if not cart.transaction_id:
        return None
    tx = db.session.get(Transaction, cart.transaction_id)
    if tx is None or tx.user_id != cart.user_id:
        return None
    return tx


# ── Mutaciones ────────────────────────────────────────────────────────────────

def clean_store_name(value) -> str:
    """Nombre del supermercado normalizado; obligatorio para crear un carrito."""
    name = ' '.join(str(value or '').split())[:STORE_NAME_MAX]
    if not name or name.startswith('/') or not any(ch.isalpha() for ch in name):
        raise CartError('store_name_required')
    return name


def start_cart(user_id: int, store_name: str | None, source: str = 'telegram') -> Cart:
    """Devuelve el carrito abierto del usuario o crea uno nuevo en ``store_name``.

    El nombre solo se exige al crear: si ya hay un carrito abierto se devuelve tal cual.
    """
    cart = get_open_cart(user_id)
    if cart is not None:
        return cart
    cart = Cart(
        user_id=user_id,
        status='open',
        source=source,
        store_name=clean_store_name(store_name),
        total=Decimal(0),
        item_count=0,
    )
    db.session.add(cart)
    db.session.flush()
    return cart


def rename_store(cart: Cart, store_name) -> None:
    cart.store_name = clean_store_name(store_name)


def recent_store_carts(user_id: int, limit: int = 3) -> list[Cart]:
    """Últimos carritos con supermercados distintos, para ofrecerlos como atajo."""
    seen, result = set(), []
    candidates = (Cart.query
                  .filter(Cart.user_id == user_id, Cart.store_name.isnot(None))
                  .order_by(Cart.id.desc())
                  .limit(30))
    for cart in candidates:
        key = normalize_name(cart.store_name)
        if key and key not in seen:
            seen.add(key)
            result.append(cart)
            if len(result) == limit:
                break
    return result


def lock_cart(cart: Cart) -> Cart:
    """Bloquea la fila del carrito hasta el próximo commit y recarga sus productos.

    Excepción a la regla del módulo: confirma la transacción en curso. Así, tras
    esperar el bloqueo, la lectura de productos ve lo que otra petición simultánea
    (otra foto, un doble toque) acaba de guardar y el total no pierde líneas.
    """
    db.session.commit()
    db.session.refresh(cart, with_for_update=True)
    return cart


def _recalc(cart: Cart) -> None:
    items = list(cart.items)
    cart.total = sum((Decimal(i.line_total) for i in items), start=Decimal(0))
    cart.item_count = len(items)
    cart.updated_at = _now()


def add_item(cart: Cart, name: str, line_total, qty=1, source: str = 'text',
             client_request_id: str | None = None) -> CartItem:
    """Agrega un producto. ``line_total`` es el monto total de la línea (precio × cantidad)."""
    if cart.status != 'open':
        raise CartError('cart_closed')
    if len(cart.items) >= MAX_ITEMS_PER_CART:
        raise CartError('cart_full')
    line_total = _to_decimal(line_total).quantize(_CENT, rounding=ROUND_HALF_UP)
    qty = _to_decimal(qty or 1, max_value=MAX_QTY)
    unit_price = (line_total / qty).quantize(_CENT, rounding=ROUND_HALF_UP)
    item = CartItem(
        name=(name or '').strip()[:200] or 'Producto',
        qty=qty,
        unit_price=unit_price,
        line_total=line_total,
        source=source,
        client_request_id=client_request_id or None,
    )
    cart.items.append(item)
    _recalc(cart)
    return item


def set_item_qty(cart: Cart, item: CartItem, qty) -> None:
    """Cambia la cantidad de un producto manteniendo su precio unitario."""
    if cart.status != 'open':
        raise CartError('cart_closed')
    qty = _to_decimal(qty, max_value=MAX_QTY)
    line_total = (Decimal(item.unit_price) * qty).quantize(_CENT, rounding=ROUND_HALF_UP)
    if line_total > MAX_AMOUNT:
        raise CartError('invalid_amount')
    item.qty = qty
    item.line_total = line_total
    _recalc(cart)


def remove_item(cart: Cart, item: CartItem) -> None:
    if cart.status != 'open':
        raise CartError('cart_closed')
    cart.items.remove(item)
    _recalc(cart)


def remove_last_item(cart: Cart) -> CartItem | None:
    if not cart.items:
        return None
    item = cart.items[-1]
    remove_item(cart, item)
    return item


def discard(cart: Cart) -> None:
    """Elimina el carrito y sus productos."""
    db.session.delete(cart)


def default_category(user_id: int) -> Category | None:
    """Categoría de gasto por defecto para el movimiento de un carrito."""
    for name in _DEFAULT_CATEGORY_NAMES:
        cat = (Category.query
               .filter(Category.name == name, Category.type == 'expense',
                       (Category.user_id == user_id) | (Category.user_id.is_(None)))
               .order_by(Category.user_id.desc())   # la del usuario antes que la global
               .first())
        if cat:
            return cat
    return (Category.query
            .filter(Category.type == 'expense',
                    (Category.user_id == user_id) | (Category.user_id.is_(None)))
            .order_by(Category.id)
            .first())


def default_description(cart: Cart) -> str:
    store = f" {cart.store_name}" if cart.store_name else ''
    return f"Carrito{store} ({cart.item_count} productos)"


def register_movement(
    cart: Cart,
    category_id: int | None = None,
    amount=None,
    tx_date: date | None = None,
    description: str | None = None,
) -> Transaction:
    """Crea el movimiento de gasto de un carrito finalizado.

    ``amount`` permite registrar un total distinto al del carrito (cambios en caja).
    """
    if cart.status != 'finalized':
        raise CartError('cart_not_finalized')
    if linked_transaction(cart) is not None:
        raise CartError('already_registered')

    if category_id is not None:
        category = Category.query.filter(
            Category.id == category_id,
            (Category.user_id == cart.user_id) | (Category.user_id.is_(None)),
        ).first()
        if category is None or category.type != 'expense':
            raise CartError('invalid_category')
    else:
        category = default_category(cart.user_id)
        if category is None:
            raise CartError('invalid_category')

    amount = _to_decimal(cart.total if amount is None else amount)
    finalized_at = _aware(cart.finalized_at)
    tx = Transaction(
        user_id=cart.user_id,
        category_id=category.id,
        type='expense',
        amount=amount,
        description=(description or '').strip()[:500] or default_description(cart),
        date=tx_date or (finalized_at.date() if finalized_at else date.today()),
    )
    db.session.add(tx)
    db.session.flush()
    cart.transaction_id = tx.id
    return tx


def finalize(cart: Cart, register: bool = False, **movement_kwargs) -> Transaction | None:
    """Cierra el carrito. Con ``register=True`` además crea el movimiento de gasto."""
    if cart.status != 'open':
        raise CartError('cart_closed')
    if not cart.items:
        raise CartError('cart_empty')
    cart.status = 'finalized'
    cart.finalized_at = _now()
    cart.updated_at = cart.finalized_at
    if register:
        return register_movement(cart, **movement_kwargs)
    return None


# ── Comparación ───────────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """Clave de comparación: minúsculas, sin acentos ni espacios repetidos."""
    text = unicodedata.normalize('NFKD', name or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return ' '.join(text.lower().split())


def _items_by_name(cart: Cart) -> dict:
    grouped = {}
    for item in cart.items:
        entry = grouped.setdefault(normalize_name(item.name), {
            'name': item.name, 'unit_price': Decimal(item.unit_price),
            'qty': Decimal(0), 'line_total': Decimal(0),
        })
        entry['qty'] += Decimal(item.qty)
        entry['line_total'] += Decimal(item.line_total)
    return grouped


def compare_carts(a: Cart, b: Cart) -> dict:
    """Compara dos carritos en orden cronológico emparejando productos por nombre.

    Devuelve ``before``/``after`` (carritos), ``total_diff`` y ``rows`` con el precio
    unitario de cada producto en ambas compras y su variación porcentual. Las filas
    con variación van primero (mayor cambio arriba); luego productos nuevos o no comprados.
    """
    if (a.finalized_at or a.started_at) > (b.finalized_at or b.started_at):
        a, b = b, a
    before, after = _items_by_name(a), _items_by_name(b)
    rows = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        diff = pct = None
        if old and new:
            diff = new['unit_price'] - old['unit_price']
            if old['unit_price']:
                pct = float(diff / old['unit_price'] * 100)
        rows.append({'name': (new or old)['name'], 'old': old, 'new': new, 'diff': diff, 'pct': pct})
    rows.sort(key=lambda r: (r['old'] is None or r['new'] is None, -abs(r['pct'] or 0)))
    return {
        'before': a,
        'after': b,
        'rows': rows,
        'total_diff': Decimal(b.total) - Decimal(a.total),
    }
