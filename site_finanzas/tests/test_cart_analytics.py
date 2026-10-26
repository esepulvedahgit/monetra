"""Analítica del carrito: tipos de producto, enriquecimiento y página «Análisis de compras»."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app import db as _db
from app.cart import analytics, enrichment
from app.cart import categories as cat
from app.cart import service as svc
from app.models import (
    Cart,
    CartItem,
    CartPendingItem,
    Category,
    ProductCatalogEntry,
    Transaction,
    User,
)

EMAIL = 'cart_analytics@example.com'
PASSWORD = 'CartPass123!'


@pytest.fixture(scope='module')
def user_id(app):
    with app.app_context():
        u = User(username='cart_analytics', email=EMAIL, role='user', email_verified=True,
                 currency_code='CLP', currency_locale='es_CL', currency_symbol='$')
        u.set_password(PASSWORD)
        _db.session.add(u)
        _db.session.commit()
        return u.id


@pytest.fixture(autouse=True)
def _clean(app, user_id):
    yield
    with app.app_context():
        cart_ids = [c.id for c in Cart.query.filter_by(user_id=user_id)]
        CartPendingItem.query.filter(CartPendingItem.cart_id.in_(cart_ids)).delete(synchronize_session=False)
        CartItem.query.filter(CartItem.cart_id.in_(cart_ids)).delete(synchronize_session=False)
        Cart.query.filter_by(user_id=user_id).delete()
        ProductCatalogEntry.query.filter_by(user_id=user_id).delete()
        Transaction.query.filter_by(user_id=user_id).delete()
        _db.session.commit()


def _purchase(user_id, store, day, items):
    """Compra finalizada el ``day`` (mediodía UTC) con ``items`` = [(nombre, precio unitario, cantidad)]."""
    cart = svc.start_cart(user_id, store, source='web')
    for name, price, qty in items:
        svc.add_item(cart, name, Decimal(price) * qty, qty=qty)
    cart.status = 'finalized'
    cart.finalized_at = datetime(day.year, day.month, day.day, 15, tzinfo=timezone.utc)
    _db.session.commit()
    return cart


def _login(app):
    client = app.test_client()
    r = client.post('/login', data={'email': EMAIL, 'password': PASSWORD})
    assert r.status_code == 302
    return client


class TestProductTypes:
    @pytest.mark.parametrize('name, expected', [
        ('Leche Colún Entera 1L', 'lacteos'),
        ('Yoghurt frutilla', 'lacteos'),
        ('Pasta dental Colgate 90g', 'cuidado_personal'),
        ('Papas fritas Lays 230 g', 'snacks'),
        ('Atún en agua', 'despensa'),
        ('Detergente líquido aroma limón', 'limpieza'),
        ('Cerveza Escudo 2 x 470 cc', 'alcohol'),
        ('Marraqueta', 'panaderia'),
        ('Pañales Babysec', 'bebe_mascotas'),
        ('Producto raro xyz', 'otros'),
    ])
    def test_keyword_classification(self, name, expected):
        assert cat.classify_local(name) == expected

    def test_size_parsing(self):
        assert cat.parse_size('Leche entera 1L') == (Decimal(1000), 'ml')
        assert cat.parse_size('Coca Cola 6x1.5l') == (Decimal('9000.0'), 'ml')
        assert cat.parse_size('Arroz 1,5 kg') == (Decimal('1500.0'), 'g')
        assert cat.parse_size('Cerveza 2 x 470 cc') == (Decimal(940), 'ml')
        assert cat.parse_size('Marraqueta') == (None, None)

    def test_generic_name_drops_size_and_brand(self):
        assert cat.generic_name('Leche Colún Entera 1L') == 'leche entera'
        assert cat.generic_name('Leche entera Soprole 1L') == 'leche entera'
        assert cat.generic_name('Coca Cola 6x1.5l') == 'coca cola'
        assert cat.generic_name('Arroz Tucapel grado 2 1 kg') == 'arroz grado'
        # Si el nombre es solo la marca, se conserva.
        assert cat.generic_name('Colún') == 'colun'

    def test_naive_bayes_learns_user_products(self):
        examples = [(f'kuchen de {f}', 'panaderia') for f in ('nuez', 'manzana', 'frambuesa', 'mora')]
        examples += [(f'sopaipilla {t}', 'panaderia') for t in ('pasada', 'congelada', 'casera')]
        examples += [(f'merken {t}', 'despensa') for t in ('ahumado', 'picante', 'natural', 'premium')]
        assert cat.classify_local('kuchen de pera', examples) == 'panaderia'
        assert cat.classify_local('sopaipilla grande', examples) == 'panaderia'


class TestEnrichment:
    def test_chain_grouping(self, app, user_id):
        with app.app_context():
            assert enrichment.chain_for('Lider Vespucio') == 'Lider'
            assert enrichment.chain_for('Líder Express') == 'Lider'
            assert enrichment.chain_for('Jumbo Costanera') == 'Jumbo'
            _purchase(user_id, 'Supermercado Pepe', date(2026, 9, 1), [('Pan', 1000, 1)])
            assert enrichment.chain_for('Supermercado Pepe Centro', user_id) == 'Supermercado Pepe'

    def test_ai_category_wins_over_local_and_is_remembered(self, app, user_id):
        with app.app_context():
            cart = svc.start_cart(user_id, 'Lider')
            item = svc.add_item(cart, 'Galletón casero', Decimal(1500), category='panaderia', generic_name='galleton casero')
            assert (item.category, item.category_source) == ('panaderia', 'ai')
            later = svc.add_item(cart, 'Galletón casero', Decimal(1500))
            assert (later.category, later.category_source) == ('panaderia', 'catalog')

    def test_user_correction_applies_everywhere(self, app, user_id):
        with app.app_context():
            old = _purchase(user_id, 'Lider', date(2026, 9, 1), [('Bebida energética Monster', 1500, 1)])
            cart = svc.start_cart(user_id, 'Jumbo')
            item = svc.add_item(cart, 'Bebida energética Monster', Decimal(1600))
            assert item.category == 'bebidas'
            changed = enrichment.set_category(user_id, item, 'snacks')
            _db.session.commit()
            assert changed == 2
            assert _db.session.get(Cart, old.id).items[0].category == 'snacks'
            # Ni la IA ni el clasificador pasan por encima de la corrección.
            again = svc.add_item(cart, 'Bebida energética Monster', Decimal(1600), category='bebidas')
            assert again.category == 'snacks'
            with pytest.raises(ValueError):
                enrichment.set_category(user_id, item, 'no_existe')

    def test_backfill_classifies_old_items(self, app, user_id):
        with app.app_context():
            cart = _purchase(user_id, 'Unimarc Centro', date(2026, 9, 1), [('Leche 1L', 1000, 1)])
            item = cart.items[0]
            item.category = item.generic_name = None
            cart.store_chain = None
            _db.session.commit()
            assert enrichment.backfill() >= 2
            assert _db.session.get(CartItem, item.id).category == 'lacteos'
            assert _db.session.get(Cart, cart.id).store_chain == 'Unimarc'

    def test_unit_measure_price(self, app, user_id):
        with app.app_context():
            cart = svc.start_cart(user_id, 'Lider')
            item = svc.add_item(cart, 'Arroz 500 g', Decimal(800))
            assert enrichment.unit_measure_price(item) == (Decimal('1600.00'), 'kg')


class TestAnalyticsReport:
    def _data(self, user_id):
        _purchase(user_id, 'Lider', date(2026, 8, 5), [('Leche entera 1L', 1000, 4), ('Detergente 3 kg', 6000, 1)])
        _purchase(user_id, 'Lider Vespucio', date(2026, 9, 5), [('Leche entera 1L', 1100, 4), ('Posta negra', 8000, 1)])
        _purchase(user_id, 'Jumbo', date(2026, 10, 5), [('Leche entera 1L', 1300, 2), ('Detergente 3 kg', 6600, 1),
                                                        ('Cerveza Escudo 470 cc', 900, 6)])

    def test_period_ranges(self):
        p = analytics.period_for('3m', date(2026, 10, 25))
        assert (p.start, p.end, p.prev_start, p.prev_end) == (date(2026, 8, 1), date(2026, 11, 1), date(2026, 5, 1), date(2026, 8, 1))
        p = analytics.period_for('year', date(2026, 10, 25))
        assert (p.start, p.prev_start) == (date(2026, 1, 1), date(2025, 1, 1))
        assert analytics.period_for('all', date(2026, 10, 25)).start is None
        assert analytics.period_for('bogus', date(2026, 10, 25)).key == '3m'

    def test_summary_categories_and_chains(self, app, user_id):
        with app.app_context():
            self._data(user_id)
            report = analytics.build_report(user_id, '3m', today=date(2026, 10, 25))
            s = report['summary']
            assert s['count'] == 3 and s['total'] == Decimal(10000 + 12400 + 14600)
            assert s['monthly_avg'] == s['total'] / 3
            by_key = {r['key']: r['amount'] for r in report['categories']}
            assert by_key == {'lacteos': Decimal(4000 + 4400 + 2600), 'limpieza': Decimal(12600),
                              'carnes': Decimal(8000), 'alcohol': Decimal(5400)}
            assert report['categories'][0]['key'] == 'limpieza'
            assert [c['chain'] for c in report['chains']] == ['Lider', 'Jumbo']
            lider = report['chains'][0]
            assert lider['count'] == 2 and lider['amount'] == Decimal(22400)
            # Tabla tipo × supermercado: la limpieza se reparte 6000 / 6600.
            row = next(r for r in report['matrix']['rows'] if r['key'] == 'limpieza')
            assert row['main_chain'] == 'Jumbo'
            assert round(row['main_pct']) == 52
            assert report['trend']['labels'] == ['08/2026', '09/2026', '10/2026']

    def test_price_index_and_savings(self, app, user_id):
        with app.app_context():
            self._data(user_id)
            prices = analytics.build_report(user_id, '3m', today=date(2026, 10, 25))['prices']
            assert [r['chain'] for r in prices['index']] == ['Lider', 'Jumbo']
            assert prices['index'][0]['index'] == pytest.approx(100)
            assert prices['index'][1]['index'] > 100
            leche = next(p for p in prices['products'] if p['key'] == 'leche entera')
            assert leche['cheapest'] == 'Lider' and leche['unit'] == 'L'
            assert leche['chains']['Lider']['avg'] == Decimal('1050.00')
            # En Jumbo pagaste 1300 por litro frente a 1050: ahorro = 2600 × 250/1300 = 500.
            assert leche['saving'] == pytest.approx(Decimal(500))
            detergente = next(p for p in prices['products'] if p['key'] == 'detergente')
            assert detergente['saving'] == pytest.approx(Decimal(600))
            assert prices['savings'] == pytest.approx(Decimal(1100))
            assert {r['key'] for r in prices['category_index']} == {'lacteos', 'limpieza'}

    def test_chain_filter_and_previous_period(self, app, user_id):
        with app.app_context():
            self._data(user_id)
            report = analytics.build_report(user_id, 'month', chain='Jumbo', today=date(2026, 10, 25))
            assert report['summary']['count'] == 1
            assert report['prices']['index'] == []   # en octubre solo hubo compra en Jumbo
            filtered = analytics.build_report(user_id, '3m', chain='Jumbo', today=date(2026, 10, 25))
            assert [c['chain'] for c in filtered['chains']] == ['Jumbo']
            assert [r['chain'] for r in filtered['prices']['index']] == ['Lider', 'Jumbo']
            assert report['summary']['prev_total'] == Decimal(0)
            assert report['available_chains'] == ['Jumbo', 'Lider']
            report = analytics.build_report(user_id, 'month', today=date(2026, 10, 25))
            assert report['summary']['total_change'] == pytest.approx((14600 - 12400) / 12400 * 100)

    def test_expense_share_uses_registered_expenses(self, app, user_id):
        with app.app_context():
            self._data(user_id)
            category = Category(name='Hogar analytics', type='expense', user_id=user_id)
            _db.session.add(category)
            _db.session.flush()
            _db.session.add(Transaction(user_id=user_id, category_id=category.id, type='expense',
                                        amount=Decimal(73000), date=date(2026, 9, 10)))
            _db.session.commit()
            s = analytics.build_report(user_id, '3m', today=date(2026, 10, 25))['summary']
            assert s['expense_share'] == pytest.approx(37000 / 73000 * 100)
            _db.session.delete(category)


class TestAnalyticsWeb:
    def test_page_renders_sections(self, app, user_id):
        with app.app_context():
            TestAnalyticsReport()._data(user_id)
        client = _login(app)
        r = client.get('/carrito/analisis?periodo=all')
        html = r.get_data(as_text=True)
        assert r.status_code == 200
        for text in ('¿En qué gastas más?', '¿Dónde compras?', '¿Dónde es más barato?',
                     'Gastas más en Limpieza del hogar', 'Qué compras en cada supermercado', 'Índice de precios'):
            assert text in html, text

    def test_page_without_purchases(self, app, user_id):
        r = _login(app).get('/carrito/analisis')
        assert r.status_code == 200
        assert 'No hay compras finalizadas en este período' in r.get_data(as_text=True)

    def test_unknown_chain_redirects(self, app, user_id):
        r = _login(app).get('/carrito/analisis?periodo=6m&supermercado=Inexistente')
        assert r.status_code == 302 and 'supermercado' not in r.headers['Location']

    def test_correct_item_type_from_detail(self, app, user_id):
        with app.app_context():
            cart = _purchase(user_id, 'Lider', date(2026, 9, 1), [('Producto raro xyz', 1000, 1)])
            cart_id, item_id = cart.id, cart.items[0].id
        client = _login(app)
        detail = client.get(f'/carrito/{cart_id}').get_data(as_text=True)
        assert 'cart-type-select' in detail
        r = client.post(f'/carrito/{cart_id}/items/{item_id}/tipo', data={'category': 'despensa'})
        assert r.status_code == 302
        with app.app_context():
            assert _db.session.get(CartItem, item_id).category == 'despensa'
            assert ProductCatalogEntry.query.filter_by(user_id=user_id, source='user').count() == 1
        assert client.post(f'/carrito/{cart_id}/items/{item_id}/tipo', data={'category': 'x'}).status_code == 302

    def test_history_shows_local_time(self, app, user_id):
        with app.app_context():
            cart = svc.start_cart(user_id, 'Lider', source='web')
            svc.add_item(cart, 'Pan', Decimal(1000))
            cart.status = 'finalized'
            cart.finalized_at = datetime(2026, 10, 25, 1, 30)   # UTC: 22:30 del 24 en Santiago
            _db.session.commit()
        html = _login(app).get('/carrito/').get_data(as_text=True)
        assert '24/10/2026 22:30' in html
