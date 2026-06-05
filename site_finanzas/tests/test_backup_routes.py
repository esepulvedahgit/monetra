"""Integration tests for the backup blueprint (admin-only routes)."""
import io
from unittest.mock import patch

import pytest


ADMIN_EMAIL = 'admin_backup@example.com'
ADMIN_PASSWORD = 'AdminPass123!'
REGULAR_EMAIL = 'regular_backup@example.com'
REGULAR_PASSWORD = 'RegPass123!'

EXPORT_URL = '/admin/backup/export'
RESTORE_URL = '/admin/backup/restore'


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _login(app, email, password):
    """Authenticate via the web login form. Returns a test client."""
    c = app.test_client()
    r = c.post('/login', data={'email': email, 'password': password})
    # Successful login → 302 redirect to dashboard (not back to /login)
    if r.status_code != 302 or '/login' in r.headers.get('Location', ''):
        raise AssertionError(
            f'Login failed for {email}: status={r.status_code} '
            f'location={r.headers.get("Location")}'
        )
    return c


def _admin_client(app, admin_user_id):
    return _login(app, ADMIN_EMAIL, ADMIN_PASSWORD)


def _regular_client(app, regular_user_id):
    return _login(app, REGULAR_EMAIL, REGULAR_PASSWORD)


def _flashes(c):
    """Return flash message strings from the session after a request."""
    with c.session_transaction() as sess:
        return [msg for _, msg in sess.get('_flashes', [])]


# ── Access control ────────────────────────────────────────────────────────────

class TestAccessControl:
    def test_export_unauthenticated(self, app):
        c = app.test_client()
        r = c.post(EXPORT_URL, data={'backup_password': 'pw', 'backup_password_confirm': 'pw'})
        assert r.status_code in (302, 401)

    def test_export_regular_user_forbidden(self, app, regular_user_id):
        c = _regular_client(app, regular_user_id)
        r = c.post(EXPORT_URL, data={'backup_password': 'pw', 'backup_password_confirm': 'pw'})
        assert r.status_code == 403

    def test_restore_unauthenticated(self, app):
        c = app.test_client()
        r = c.post(RESTORE_URL, data={
            'account_password': 'pw', 'backup_password': 'pw', 'confirm': 'RESTAURAR',
        })
        assert r.status_code in (302, 401)

    def test_restore_regular_user_forbidden(self, app, regular_user_id):
        c = _regular_client(app, regular_user_id)
        r = c.post(RESTORE_URL, data={
            'account_password': 'pw',
            'backup_password': 'bp',
            'confirm': 'RESTAURAR',
            'backup_file': (io.BytesIO(b'data'), 'test.mntrbak'),
        }, content_type='multipart/form-data')
        assert r.status_code == 403


# ── Export ────────────────────────────────────────────────────────────────────

class TestExport:
    def test_empty_password_rejected(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        r = c.post(EXPORT_URL, data={'backup_password': '', 'backup_password_confirm': ''})
        assert r.status_code == 302
        msgs = _flashes(c)
        assert any('vacía' in m for m in msgs)

    def test_password_mismatch_rejected(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        r = c.post(EXPORT_URL, data={'backup_password': 'abc', 'backup_password_confirm': 'xyz'})
        assert r.status_code == 302
        msgs = _flashes(c)
        assert any('no coinciden' in m for m in msgs)

    def test_valid_export_returns_file(self, app, admin_user_id):
        fake_blob = b'MNTRBAK1' + b'\xAB' * 64
        c = _admin_client(app, admin_user_id)
        with patch('app.backup.routes.make_backup', return_value=fake_blob):
            r = c.post(EXPORT_URL, data={
                'backup_password': 'strong-pass-123',
                'backup_password_confirm': 'strong-pass-123',
            })
        assert r.status_code == 200
        assert r.content_type == 'application/octet-stream'
        assert r.data == fake_blob

    def test_service_error_hides_internal_details(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        with patch('app.backup.routes.make_backup',
                   side_effect=RuntimeError('mysqldump: Access denied for root@172.0.0.1')):
            r = c.post(EXPORT_URL, data={
                'backup_password': 'strong-pass-123',
                'backup_password_confirm': 'strong-pass-123',
            })
        assert r.status_code == 302
        msgs = _flashes(c)
        # Internal details must NOT reach the UI
        assert not any('mysqldump' in m or 'Access denied' in m or 'root@' in m for m in msgs)
        assert len(msgs) > 0


# ── Restore ───────────────────────────────────────────────────────────────────

class TestRestore:
    def _post(self, c, *, account_password=ADMIN_PASSWORD,
              backup_password='bp', confirm='RESTAURAR',
              file_bytes=b'MNTRBAK1\x00'):
        return c.post(RESTORE_URL, data={
            'account_password': account_password,
            'backup_password': backup_password,
            'confirm': confirm,
            'backup_file': (io.BytesIO(file_bytes), 'backup.mntrbak'),
        }, content_type='multipart/form-data')

    def test_wrong_account_password_rejected(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        r = self._post(c, account_password='wrong-password')
        assert r.status_code == 302
        msgs = _flashes(c)
        assert any('incorrecta' in m for m in msgs)

    def test_wrong_confirm_word_rejected(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        r = self._post(c, confirm='BORRAR')
        assert r.status_code == 302
        msgs = _flashes(c)
        assert any('RESTAURAR' in m for m in msgs)

    def test_no_file_rejected(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        r = c.post(RESTORE_URL, data={
            'account_password': ADMIN_PASSWORD,
            'backup_password': 'bp',
            'confirm': 'RESTAURAR',
        })
        assert r.status_code == 302
        msgs = _flashes(c)
        assert any('seleccionar' in m for m in msgs)

    def test_empty_backup_password_rejected(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        r = self._post(c, backup_password='')
        assert r.status_code == 302
        msgs = _flashes(c)
        assert any('vacía' in m.lower() for m in msgs)

    def test_invalid_file_shows_user_safe_error(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        with patch('app.backup.routes.read_backup',
                   side_effect=ValueError('cabecera inválida')):
            r = self._post(c)
        assert r.status_code == 302
        msgs = _flashes(c)
        assert any('cabecera inválida' in m for m in msgs)

    def test_service_restore_error_hides_internals(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        with (
            patch('app.backup.routes.read_backup', return_value=b'-- sql'),
            patch('app.backup.routes._save_safety_snapshot', return_value=None),
            patch('app.backup.routes.restore_database',
                  side_effect=RuntimeError('mysql: Connection refused to 10.0.0.1:3306')),
        ):
            r = self._post(c)
        assert r.status_code == 302
        msgs = _flashes(c)
        assert not any('mysql:' in m or '10.0.0.1' in m or 'Connection refused' in m
                       for m in msgs)
        assert len(msgs) > 0

    def test_successful_restore_redirects_to_login(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        with (
            patch('app.backup.routes.read_backup', return_value=b'-- sql'),
            patch('app.backup.routes._save_safety_snapshot', return_value='/tmp/snap.sql.gz'),
            patch('app.backup.routes.restore_database'),
        ):
            r = self._post(c)
        assert r.status_code == 302
        assert '/login' in r.headers.get('Location', '')

    def test_unexpected_read_error_hides_internals(self, app, admin_user_id):
        c = _admin_client(app, admin_user_id)
        with patch('app.backup.routes.read_backup',
                   side_effect=MemoryError('out of memory reading 4GB file')):
            r = self._post(c)
        assert r.status_code == 302
        msgs = _flashes(c)
        assert not any('4GB' in m or 'MemoryError' in m for m in msgs)
        assert len(msgs) > 0
