"""Integration tests for authenticated Android APK distribution."""
import io
from unittest.mock import patch
import zipfile

import pytest

from app import db
from app.models import MobileRelease


ADMIN_EMAIL = 'admin_backup@example.com'
ADMIN_PASSWORD = 'AdminPass123!'
REGULAR_EMAIL = 'regular_backup@example.com'
REGULAR_PASSWORD = 'RegPass123!'
FINGERPRINT = 'AA' * 32


def _login(app, email, password):
    client = app.test_client()
    response = client.post('/login', data={'email': email, 'password': password})
    assert response.status_code == 302
    assert '/login' not in response.headers.get('Location', '')
    return client


def _apk(payload=b'apk'):
    """Return a tiny structurally valid APK-shaped ZIP for upload tests."""
    content = io.BytesIO()
    with zipfile.ZipFile(content, 'w') as archive:
        archive.writestr('AndroidManifest.xml', b'<manifest/>')
        archive.writestr('classes.dex', payload)
    return content.getvalue()


@pytest.fixture(autouse=True)
def release_store(app, tmp_path):
    app.config.update(
        MOBILE_RELEASES_DIR=str(tmp_path),
        MOBILE_APK_SIGNER_SHA256=FINGERPRINT,
        MAX_MOBILE_APK_BYTES=1024 * 1024,
    )
    with app.app_context():
        MobileRelease.query.delete()
        db.session.commit()
    yield tmp_path
    with app.app_context():
        MobileRelease.query.delete()
        db.session.commit()


def _publish(client, *, filename='monetra.apk', content=None, password=ADMIN_PASSWORD,
             version='1.0.0', version_code='1'):
    if content is None:
        content = _apk()
    return client.post(
        '/admin/mobile/publish',
        data={
            'account_password': password,
            'version': version,
            'version_code': version_code,
            'notes': 'Primera versión',
            'apk_file': (io.BytesIO(content), filename),
        },
        content_type='multipart/form-data',
    )


class TestMobileReleaseAccess:
    def test_authenticated_user_menu_links_to_android_app_below_settings(self, app, regular_user_id):
        client = _login(app, REGULAR_EMAIL, REGULAR_PASSWORD)

        response = client.get('/dashboard')

        assert response.status_code == 200
        settings_position = response.data.index(b'href="/configurar"')
        mobile_position = response.data.index(b'href="/mobile"')
        guide_position = response.data.index(b'href="/ayuda"')
        assert settings_position < mobile_position < guide_position

    def test_only_authenticated_users_can_view_and_download_the_current_apk(self, app, regular_user_id):
        unauthenticated = app.test_client()
        assert unauthenticated.get('/mobile').status_code in (302, 401)
        assert unauthenticated.get('/mobile/download').status_code in (302, 401)

        client = _login(app, REGULAR_EMAIL, REGULAR_PASSWORD)
        assert client.get('/mobile').status_code == 200
        assert client.get('/mobile/download').status_code == 404

    def test_only_first_admin_can_open_publish_page(self, app, regular_user_id):
        regular = _login(app, REGULAR_EMAIL, REGULAR_PASSWORD)
        assert regular.get('/admin/mobile').status_code == 403


class TestMobileReleasePublication:
    def test_publish_requires_password_before_signature_verification(self, app, admin_user_id):
        client = _login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        with patch('app.mobile_releases.service.verify_apk_signature') as verify:
            response = _publish(client, password='wrong')
        assert response.status_code == 302
        verify.assert_not_called()

    def test_publish_verifies_fingerprint_and_serves_authenticated_download(
        self, app, admin_user_id, regular_user_id, release_store
    ):
        admin = _login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        with patch('app.mobile_releases.service.verify_apk_signature', return_value=FINGERPRINT):
            apk = _apk(b'signed-apk')
            response = _publish(admin, content=apk)
        assert response.status_code == 302
        assert (release_store / 'monetra-current.apk').read_bytes() == apk

        with app.app_context():
            release = MobileRelease.query.one()
            assert release.is_current is True
            assert release.sha256
            assert release.certificate_sha256 == FINGERPRINT

        regular = _login(app, REGULAR_EMAIL, REGULAR_PASSWORD)
        download = regular.get('/mobile/download')
        assert download.status_code == 200
        assert download.data == apk
        assert download.headers['X-Content-Type-Options'] == 'nosniff'

    def test_new_release_replaces_only_current_binary_and_retains_metadata(
        self, app, admin_user_id, release_store
    ):
        admin = _login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        with patch('app.mobile_releases.service.verify_apk_signature', return_value=FINGERPRINT):
            one = _apk(b'one')
            two = _apk(b'two')
            assert _publish(admin, version='1.0.0', version_code='1', content=one).status_code == 302
            assert _publish(admin, version='1.1.0', version_code='2', content=two).status_code == 302

        assert (release_store / 'monetra-current.apk').read_bytes() == two
        assert list(release_store.glob('*.apk')) == [release_store / 'monetra-current.apk']
        with app.app_context():
            releases = MobileRelease.query.order_by(MobileRelease.version_code).all()
            assert len(releases) == 2
            assert [release.is_current for release in releases] == [False, True]

    def test_rejects_wrong_extension_invalid_zip_or_wrong_certificate(self, app, admin_user_id):
        admin = _login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert _publish(admin, filename='monetra.zip').status_code == 302
        assert _publish(admin, content=b'not-a-zip').status_code == 302
        with patch('app.mobile_releases.service.verify_apk_signature', return_value='BB' * 32):
            assert _publish(admin).status_code == 302
        with app.app_context():
            assert MobileRelease.query.count() == 0
