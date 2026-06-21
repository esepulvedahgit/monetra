"""Unit tests for app.backup.service — pure Python, no Flask context required."""
import base64
import gzip
import json
import os
import struct

import pytest

from app.backup.service import (
    MAGIC,
    SALT_LEN,
    _derive_key,
    _safe_gunzip,
    make_backup,
    read_backup,
)

FAKE_SQL = b'-- Monetra unit test\nCREATE TABLE test_tbl (id INT);\n'
PASSWORD = 'correct-horse-battery-staple'


# ── _safe_gunzip ──────────────────────────────────────────────────────────────

class TestSafeGunzip:
    def test_roundtrip(self):
        data = b'hello compressed world'
        assert _safe_gunzip(gzip.compress(data)) == data

    def test_zip_bomb_rejected(self):
        big = b'A' * (2 * 1024 * 1024)
        compressed = gzip.compress(big)
        with pytest.raises(ValueError, match='supera el límite'):
            _safe_gunzip(compressed, limit=1024 * 1024)

    def test_exact_limit_allowed(self):
        data = b'X' * 1024
        assert len(_safe_gunzip(gzip.compress(data), limit=1024)) == 1024

    def test_over_limit_by_one_rejected(self):
        data = b'X' * 1025
        compressed = gzip.compress(data)
        with pytest.raises(ValueError):
            _safe_gunzip(compressed, limit=1024)

    def test_invalid_data_raises(self):
        with pytest.raises(Exception):
            _safe_gunzip(b'not gzip data at all')


# ── _derive_key ───────────────────────────────────────────────────────────────

class TestDeriveKey:
    def test_produces_32_byte_key(self):
        key = _derive_key('password', os.urandom(32))
        decoded = base64.urlsafe_b64decode(key + b'==')
        assert len(decoded) == 32

    def test_different_salts_give_different_keys(self):
        s1, s2 = os.urandom(32), os.urandom(32)
        assert _derive_key('password', s1) != _derive_key('password', s2)

    def test_different_passwords_give_different_keys(self):
        salt = os.urandom(32)
        assert _derive_key('pass1', salt) != _derive_key('pass2', salt)

    def test_same_inputs_give_same_key(self):
        salt = os.urandom(32)
        assert _derive_key('password', salt) == _derive_key('password', salt)


# ── make_backup / read_backup round-trip ─────────────────────────────────────

class TestBackupRoundTrip:
    def test_basic_roundtrip(self, monkeypatch):
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.setenv('DB_NAME', 'test_db')
        monkeypatch.setattr('app.backup.service.dump_database', lambda: FAKE_SQL)

        blob = make_backup(PASSWORD)

        assert blob.startswith(MAGIC)
        assert len(blob) > len(MAGIC) + SALT_LEN
        assert read_backup(blob, PASSWORD) == FAKE_SQL

    def test_wrong_password_rejected(self, monkeypatch):
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.setenv('DB_NAME', 'test_db')
        monkeypatch.setattr('app.backup.service.dump_database', lambda: FAKE_SQL)

        blob = make_backup(PASSWORD)
        with pytest.raises(ValueError, match='Contraseña de respaldo incorrecta'):
            read_backup(blob, 'wrong-password')

    def test_empty_password_rejected(self, monkeypatch):
        monkeypatch.setattr('app.backup.service.dump_database', lambda: FAKE_SQL)
        with pytest.raises(ValueError, match='no puede estar vacía'):
            make_backup('')

    def test_sql_not_in_blob(self, monkeypatch):
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.setenv('DB_NAME', 'test_db')
        monkeypatch.setattr('app.backup.service.dump_database', lambda: FAKE_SQL)

        blob = make_backup(PASSWORD)
        assert b'CREATE TABLE' not in blob
        assert FAKE_SQL not in blob

    def test_two_backups_are_unique(self, monkeypatch):
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.setenv('DB_NAME', 'test_db')
        monkeypatch.setattr('app.backup.service.dump_database', lambda: FAKE_SQL)

        assert make_backup(PASSWORD) != make_backup(PASSWORD)

    def test_blob_starts_with_magic(self, monkeypatch):
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.setenv('DB_NAME', 'test_db')
        monkeypatch.setattr('app.backup.service.dump_database', lambda: FAKE_SQL)

        blob = make_backup(PASSWORD)
        assert blob[:len(MAGIC)] == MAGIC


# ── read_backup validation ────────────────────────────────────────────────────

def _craft_blob(db_name='test_db', fmt='monetra-backup/1',
                sql=FAKE_SQL, password=PASSWORD):
    """Build a syntactically valid encrypted blob without calling dump_database."""
    from cryptography.fernet import Fernet
    from app.backup.service import _derive_key

    compressed = gzip.compress(sql)
    manifest = {
        'format': fmt,
        'db_name': db_name,
        'created_at': '2026-01-01T00:00:00+00:00',
        'app_version': '2.6',
    }
    manifest_bytes = json.dumps(manifest).encode()
    header = struct.pack('>I', len(manifest_bytes)) + manifest_bytes
    plaintext = header + compressed
    salt = os.urandom(SALT_LEN)
    key = _derive_key(password, salt)
    token = Fernet(key).encrypt(plaintext)
    return MAGIC + salt + token


class TestReadBackupValidation:
    def test_bad_magic_rejected(self):
        with pytest.raises(ValueError, match='cabecera inválida'):
            read_backup(b'BADMAGIC' + b'\x00' * 200, PASSWORD)

    def test_truncated_after_magic(self):
        with pytest.raises(ValueError, match='corrupto o truncado'):
            read_backup(MAGIC + b'\x00' * 5, PASSWORD)

    def test_wrong_db_name_rejected(self, monkeypatch):
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.setenv('DB_NAME', 'staging_db')
        blob = _craft_blob(db_name='prod_db')
        with pytest.raises(ValueError, match="'prod_db'"):
            read_backup(blob, PASSWORD)

    def test_h9_empty_db_name_in_manifest_rejected(self, monkeypatch):
        """H9: empty db_name must be rejected when the server has a known DB_NAME."""
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.setenv('DB_NAME', 'my_production_db')
        blob = _craft_blob(db_name='')
        with pytest.raises(ValueError, match='sin nombre'):
            read_backup(blob, PASSWORD)

    def test_unknown_format_rejected(self, monkeypatch):
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.setenv('DB_NAME', 'test_db')
        blob = _craft_blob(db_name='test_db', fmt='other-tool/v99')
        with pytest.raises(ValueError, match='Formato de respaldo no reconocido'):
            read_backup(blob, PASSWORD)

    def test_db_name_match_accepted(self, monkeypatch):
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.setenv('DB_NAME', 'same_db')
        blob = _craft_blob(db_name='same_db')
        result = read_backup(blob, PASSWORD)
        assert result == FAKE_SQL

    def test_no_expected_db_skips_name_check(self, monkeypatch):
        """When DB_NAME env var is not set, any db_name in manifest is accepted."""
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.delenv('DB_NAME', raising=False)
        blob = _craft_blob(db_name='any_db')
        assert read_backup(blob, PASSWORD) == FAKE_SQL

    def test_zip_bomb_in_backup_rejected(self, monkeypatch):
        """A blob whose SQL decompresses beyond the configured limit is rejected."""
        monkeypatch.setattr('app.backup.service.PBKDF2_ITERATIONS', 1)
        monkeypatch.setenv('DB_NAME', 'test_db')
        monkeypatch.setattr('app.backup.service.MAX_DECOMPRESSED_BYTES', 512 * 1024)

        big_sql = b'-- ' + b'A' * (1024 * 1024)  # 1 MB, over 512 KB limit
        blob = _craft_blob(db_name='test_db', sql=big_sql)
        with pytest.raises(ValueError, match='supera el límite'):
            read_backup(blob, PASSWORD)
