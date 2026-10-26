"""Completa productos y compras con los datos que usa la analítica del carrito.

Tipo de producto, en orden de prioridad: la corrección del usuario (vía catálogo),
la IA al leer la etiqueta, una lectura anterior de la IA guardada en el catálogo y,
por último, el clasificador local. Las funciones no hacen commit, salvo
``backfill``, que corre una vez al iniciar el servidor.
"""
from decimal import Decimal

from app import db
from app.cart import categories as cat
from app.models import Cart, CartItem, ProductCatalogEntry

# Cadenas conocidas: el nombre que escribe el usuario se agrupa bajo la cadena.
KNOWN_CHAINS = {
    'lider': 'Lider', 'express de lider': 'Lider', 'walmart': 'Walmart', 'jumbo': 'Jumbo',
    'santa isabel': 'Santa Isabel', 'unimarc': 'Unimarc', 'tottus': 'Tottus', 'acuenta': 'aCuenta',
    'alvi': 'Alvi', 'mayorista 10': 'Mayorista 10', 'super 10': 'Super 10', 'ekono': 'Ekono',
    'oxxo': 'OXXO', 'ok market': 'OK Market', 'montserrat': 'Montserrat', 'spid': 'Spid',
    'cugat': 'Cugat', 'carrefour': 'Carrefour', 'dia': 'Dia', 'mercadona': 'Mercadona',
    'soriana': 'Soriana', 'chedraui': 'Chedraui', 'exito': 'Éxito', 'olimpica': 'Olímpica',
    'plaza vea': 'Plaza Vea', 'wong': 'Wong', 'metro': 'Metro', 'coto': 'Coto', 'disco': 'Disco',
}
_BATCH = 500


def chain_for(store_name: str | None, user_id: int | None = None) -> str | None:
    """Cadena del supermercado: conocida, una ya usada por el usuario o el nombre tal cual."""
    if not store_name:
        return None
    text = f" {cat.normalize(store_name)} "
    best = None
    for key, chain in KNOWN_CHAINS.items():
        if f" {key} " in text and (best is None or len(key) > len(best[0])):
            best = (key, chain)
    if best:
        return best[1]
    if user_id is not None:
        # "Supermercado Pepe Centro" se agrupa con "Supermercado Pepe" si ya existía.
        chains = {c for (c,) in db.session.query(Cart.store_chain)
                  .filter(Cart.user_id == user_id, Cart.store_chain.isnot(None)).distinct()}
        for chain in sorted(chains, key=len, reverse=True):
            if f" {cat.normalize(chain)} " in text:
                return chain
    return ' '.join(store_name.split())[:120]


def name_key(item_name: str | None, generic: str | None = None) -> str:
    return (cat.generic_name(generic) if generic else '') or cat.generic_name(item_name) or cat.normalize(item_name)[:120]


def _catalog(user_id: int, key: str) -> ProductCatalogEntry | None:
    return ProductCatalogEntry.query.filter_by(user_id=user_id, name_key=key).first()


def _examples(user_id: int) -> list[tuple[str, str]]:
    return [(e.name_key, e.category) for e in ProductCatalogEntry.query.filter_by(user_id=user_id).all()]


def _remember(user_id: int, key: str, category: str, source: str) -> None:
    entry = _catalog(user_id, key)
    if entry is None:
        db.session.add(ProductCatalogEntry(user_id=user_id, name_key=key, category=category, source=source))
    elif source == 'user' or entry.source != 'user':
        entry.category, entry.source = category, source


def enrich_item(item: CartItem, user_id: int, *, ai_category: str | None = None, ai_generic: str | None = None,
                examples: list[tuple[str, str]] | None = None) -> None:
    """Asigna tipo, nombre genérico y tamaño a un producto recién agregado."""
    key = name_key(item.name, ai_generic)
    item.generic_name = key or None
    item.size_amount, item.size_unit = cat.parse_size(item.name)
    if item.size_amount is None and ai_generic:
        item.size_amount, item.size_unit = cat.parse_size(ai_generic)

    entry = _catalog(user_id, key) if key else None
    if entry is not None and entry.source == 'user':
        item.category, item.category_source = entry.category, 'catalog'
    elif cat.is_valid(ai_category):
        item.category, item.category_source = ai_category, 'ai'
        if key:
            _remember(user_id, key, ai_category, 'ai')
    elif entry is not None:
        item.category, item.category_source = entry.category, 'catalog'
    else:
        item.category = cat.classify_local(item.name, examples if examples is not None else _examples(user_id))
        item.category_source = 'local'


def set_category(user_id: int, item: CartItem, category: str) -> int:
    """Corrección del usuario: fija el tipo del producto y de sus otras compras.

    Devuelve cuántos productos cambió. Lanza ValueError si el tipo no existe.
    """
    if not cat.is_valid(category):
        raise ValueError('invalid_category')
    key = item.generic_name or name_key(item.name)
    item.generic_name = key
    _remember(user_id, key, category, 'user')
    same = (CartItem.query.join(Cart, Cart.id == CartItem.cart_id)
            .filter(Cart.user_id == user_id, CartItem.generic_name == key).all())
    changed = 0
    for other in {*same, item}:
        if other.category != category or other.category_source != 'user':
            changed += 1
        other.category, other.category_source = category, 'user'
    return changed


def backfill() -> int:
    """Completa cadena y tipo de lo guardado antes de la analítica. Idempotente."""
    done = 0
    for cart in Cart.query.filter(Cart.store_chain.is_(None), Cart.store_name.isnot(None)).all():
        cart.store_chain = chain_for(cart.store_name, cart.user_id)
        done += 1
    db.session.commit()

    examples_by_user: dict[int, list] = {}
    while True:
        rows = (db.session.query(CartItem, Cart.user_id).join(Cart, Cart.id == CartItem.cart_id)
                .filter(CartItem.category.is_(None)).limit(_BATCH).all())
        if not rows:
            break
        for item, user_id in rows:
            if user_id not in examples_by_user:
                examples_by_user[user_id] = _examples(user_id)
            enrich_item(item, user_id, examples=examples_by_user[user_id])
            done += 1
        db.session.commit()
    return done


def unit_measure_price(item) -> tuple[Decimal | None, str | None]:
    """Precio por kilo o por litro según el envase, para comparar tamaños distintos."""
    if not item.size_amount or not item.size_unit or item.size_unit not in ('g', 'ml'):
        return None, None
    per = (Decimal(item.unit_price) * 1000 / Decimal(item.size_amount)).quantize(Decimal('0.01'))
    return per, 'kg' if item.size_unit == 'g' else 'L'
