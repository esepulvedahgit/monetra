"""Sesiones móviles por dispositivo: renovar en un teléfono no cierra la sesión de otro."""
from datetime import datetime, timezone

from app import db
from app.models import MobileSession, User

LOGIN = {'email': 'test@example.com', 'password': 'Password123!'}


def _login(client):
    r = client.post('/api/v1/login', json=LOGIN)
    assert r.status_code == 200, r.data
    return r.get_json()


def _refresh(client, refresh_token):
    return client.post('/api/v1/refresh', headers={'Authorization': f'Bearer {refresh_token}'})


def _me(client, access_token):
    return client.get('/api/v1/me', headers={'Authorization': f'Bearer {access_token}'})


class TestMobileSessionsPerDevice:
    def test_refresh_on_one_device_keeps_the_other_signed_in(self, client, user):
        phone = _login(client)
        tablet = _login(client)

        phone_refreshed = _refresh(client, phone['refresh_token'])
        assert phone_refreshed.status_code == 200

        # La tablet guardó su refresh token en el acceso rápido y lo usa al desbloquear.
        tablet_refreshed = _refresh(client, tablet['refresh_token'])
        assert tablet_refreshed.status_code == 200
        assert _me(client, tablet_refreshed.get_json()['access_token']).status_code == 200
        assert _me(client, phone_refreshed.get_json()['access_token']).status_code == 200

    def test_refresh_token_is_single_use_within_its_device(self, client, user):
        tokens = _login(client)
        rotated = _refresh(client, tokens['refresh_token'])
        assert rotated.status_code == 200
        # El access token anterior de la misma sesión deja de valer al renovar.
        assert _me(client, tokens['access_token']).status_code == 401

        replay = _refresh(client, tokens['refresh_token'])
        assert replay.status_code == 401
        # Reusar un refresh token ya rotado delata una copia: se cierra esa sesión.
        assert _refresh(client, rotated.get_json()['refresh_token']).status_code == 401

    def test_logout_only_closes_that_device(self, client, user):
        phone = _login(client)
        tablet = _login(client)
        assert client.post('/api/v1/logout', headers={'Authorization': f"Bearer {phone['refresh_token']}"}).status_code == 200
        assert _me(client, phone['access_token']).status_code == 401
        assert _refresh(client, phone['refresh_token']).status_code == 401
        assert _me(client, tablet['access_token']).status_code == 200
        assert _refresh(client, tablet['refresh_token']).status_code == 200

    def test_password_change_closes_every_device(self, app, client, user):
        phone = _login(client)
        tablet = _login(client)
        r = client.post('/api/v1/me/password', headers={'Authorization': f"Bearer {phone['access_token']}"}, json={
            'current_password': 'Password123!', 'new_password': 'NuevaClave123!', 'confirm_password': 'NuevaClave123!'})
        assert r.status_code == 200, r.data
        assert _refresh(client, phone['refresh_token']).status_code == 401
        assert _refresh(client, tablet['refresh_token']).status_code == 401
        with app.app_context():
            u = User.query.filter_by(email=LOGIN['email']).first()
            assert MobileSession.query.filter_by(user_id=u.id, revoked_at=None).count() == 0
            u.set_password(LOGIN['password'])
            # Los tokens de otros tests se emiten en el mismo segundo: no deben quedar vencidos.
            u.api_sessions_valid_after = None
            db.session.commit()

    def test_session_records_last_use(self, app, client, user):
        tokens = _login(client)
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        assert _refresh(client, tokens['refresh_token']).status_code == 200
        with app.app_context():
            u = User.query.filter_by(email=LOGIN['email']).first()
            session = MobileSession.query.filter_by(user_id=u.id).order_by(MobileSession.id.desc()).first()
            assert session.version == 1 and session.last_used_at.replace(tzinfo=None) >= before
