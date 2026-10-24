from datetime import date
from decimal import Decimal, InvalidOperation

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app import db
from app.audit.events import CART_FINALIZE, CART_MOVEMENT
from app.audit.logger import log_event
from app.cart import cart_bp
from app.cart import service as svc
from app.models import Cart, CartItem, Category

_HISTORY_LIMIT = 100

_ERROR_MESSAGES = {
    'invalid_amount': lambda: _('El monto no es válido.'),
    'invalid_category': lambda: _('La categoría seleccionada no es válida.'),
    'cart_closed': lambda: _('Este carrito ya fue finalizado.'),
    'cart_empty': lambda: _('El carrito no tiene productos.'),
    'cart_full': lambda: _('El carrito alcanzó el máximo de productos.'),
    'cart_not_finalized': lambda: _('Finaliza el carrito antes de registrar el movimiento.'),
    'already_registered': lambda: _('Este carrito ya tiene un movimiento registrado.'),
}


def _flash_error(exc: svc.CartError) -> None:
    message = _ERROR_MESSAGES.get(exc.code)
    flash(message() if message else _('No se pudo completar la operación.'), 'warning')


def _own_cart_or_404(cart_id: int) -> Cart:
    cart = svc.get_user_cart(current_user.id, cart_id)
    if cart is None:
        abort(404)
    return cart


def _expense_categories():
    return (Category.query
            .filter(Category.type == 'expense',
                    (Category.user_id == current_user.id) | (Category.user_id.is_(None)))
            .order_by(Category.name)
            .all())


def _parse_decimal(value: str | None) -> Decimal | None:
    raw = (value or '').strip().replace(' ', '')
    if not raw:
        return None
    # El input HTML type=number envía punto decimal; toleramos coma por si acaso.
    try:
        return Decimal(raw.replace(',', '.'))
    except InvalidOperation:
        return None


def _finalized_carts():
    return (Cart.query
            .filter_by(user_id=current_user.id, status='finalized')
            .order_by(Cart.finalized_at.desc(), Cart.id.desc())
            .limit(_HISTORY_LIMIT)
            .all())


# ── Vistas ────────────────────────────────────────────────────────────────────

@cart_bp.route('/')
@login_required
def index():
    stale = svc.close_stale_cart(current_user.id)
    if stale is not None:
        db.session.commit()
        flash(_('Tu carrito anterior estaba inactivo y se guardó automáticamente.'), 'info')
    open_cart = svc.get_open_cart(current_user.id)
    history = _finalized_carts()

    totals = [Decimal(c.total) for c in history]
    stats = {
        'count': len(history),
        'average': (sum(totals, start=Decimal(0)) / len(totals)) if totals else Decimal(0),
        'last': totals[0] if totals else None,
        'previous': totals[1] if len(totals) > 1 else None,
    }
    chart = [
        {'label': c.finalized_at.strftime('%d/%m/%Y') if c.finalized_at else '', 'total': float(c.total)}
        for c in reversed(history[:12])
    ]
    return render_template('cart/index.html', open_cart=open_cart, history=history,
                           stats=stats, chart=chart)


@cart_bp.route('/<int:cart_id>')
@login_required
def detail(cart_id):
    cart = _own_cart_or_404(cart_id)
    others = [c for c in _finalized_carts() if c.id != cart.id]
    return render_template('cart/detail.html', cart=cart,
                           movement=svc.linked_transaction(cart),
                           categories=_expense_categories(),
                           default_category=svc.default_category(current_user.id),
                           default_description=svc.default_description(cart),
                           others=others, today=date.today())


@cart_bp.route('/comparar')
@login_required
def compare():
    a = _own_cart_or_404(request.args.get('a', type=int) or 0)
    b = _own_cart_or_404(request.args.get('b', type=int) or 0)
    result = svc.compare_carts(a, b)
    return render_template('cart/compare.html', a=result['before'], b=result['after'],
                           rows=result['rows'], total_diff=result['total_diff'])


# ── Acciones ──────────────────────────────────────────────────────────────────

@cart_bp.route('/nuevo', methods=['POST'])
@login_required
def start():
    svc.close_stale_cart(current_user.id)
    cart = svc.start_cart(current_user.id, source='web',
                          store_name=request.form.get('store_name'))
    db.session.commit()
    return redirect(url_for('cart.detail', cart_id=cart.id))


@cart_bp.route('/<int:cart_id>/items', methods=['POST'])
@login_required
def add_item(cart_id):
    cart = _own_cart_or_404(cart_id)
    name = (request.form.get('name') or '').strip()
    amount = _parse_decimal(request.form.get('amount'))
    qty = _parse_decimal(request.form.get('qty')) or Decimal(1)
    if not name or amount is None:
        flash(_('Indica el producto y su precio.'), 'warning')
        return redirect(url_for('cart.detail', cart_id=cart.id))
    try:
        # El formulario web pide el precio unitario.
        svc.add_item(cart, name, amount * qty, qty=qty, source='web')
        db.session.commit()
    except svc.CartError as exc:
        db.session.rollback()
        _flash_error(exc)
    return redirect(url_for('cart.detail', cart_id=cart.id))


@cart_bp.route('/<int:cart_id>/items/<int:item_id>/eliminar', methods=['POST'])
@login_required
def remove_item(cart_id, item_id):
    cart = _own_cart_or_404(cart_id)
    item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first_or_404()
    try:
        svc.remove_item(cart, item)
        db.session.commit()
    except svc.CartError as exc:
        db.session.rollback()
        _flash_error(exc)
    return redirect(url_for('cart.detail', cart_id=cart.id))


@cart_bp.route('/<int:cart_id>/finalizar', methods=['POST'])
@login_required
def finalize(cart_id):
    cart = _own_cart_or_404(cart_id)
    register = request.form.get('register') == '1'
    try:
        tx = svc.finalize(cart, register=register)
        log_event(CART_FINALIZE, user_id=current_user.id,
                  description=f"cart={cart.id} total={cart.total} items={cart.item_count}", request=request)
        if tx is not None:
            log_event(CART_MOVEMENT, user_id=current_user.id,
                      description=f"cart={cart.id} amount={tx.amount}", request=request)
        db.session.commit()
    except svc.CartError as exc:
        db.session.rollback()
        _flash_error(exc)
        return redirect(url_for('cart.detail', cart_id=cart.id))
    if register:
        flash(_('Carrito finalizado y agregado a tus movimientos.'), 'success')
    else:
        flash(_('Carrito guardado. Puedes registrarlo como movimiento cuando quieras.'), 'success')
    return redirect(url_for('cart.detail', cart_id=cart.id))


@cart_bp.route('/<int:cart_id>/registrar', methods=['POST'])
@login_required
def register_movement(cart_id):
    cart = _own_cart_or_404(cart_id)
    amount = _parse_decimal(request.form.get('amount'))
    try:
        tx_date = date.fromisoformat(request.form.get('date') or '')
    except ValueError:
        tx_date = None
    try:
        tx = svc.register_movement(
            cart,
            category_id=request.form.get('category_id', type=int),
            amount=amount,
            tx_date=tx_date,
            description=request.form.get('description'),
        )
        log_event(CART_MOVEMENT, user_id=current_user.id,
                  description=f"cart={cart.id} amount={tx.amount}", request=request)
        db.session.commit()
    except svc.CartError as exc:
        db.session.rollback()
        _flash_error(exc)
        return redirect(url_for('cart.detail', cart_id=cart.id))
    flash(_('Movimiento registrado a partir del carrito.'), 'success')
    return redirect(url_for('cart.detail', cart_id=cart.id))


@cart_bp.route('/<int:cart_id>/eliminar', methods=['POST'])
@login_required
def delete(cart_id):
    cart = _own_cart_or_404(cart_id)
    svc.discard(cart)
    db.session.commit()
    flash(_('Carrito eliminado.'), 'success')
    return redirect(url_for('cart.index'))
