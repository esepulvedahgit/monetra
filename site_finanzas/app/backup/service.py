"""
Backup / restore service for Monetra.

File format (.mntrbak):
  [MAGIC 8 bytes] [SALT 32 bytes] [Fernet-encrypted payload]

Fernet payload (after decryption):
  [manifest_len 4 bytes big-endian] [manifest JSON utf-8] [gzip-compressed SQL]

The FIELD_ENCRYPTION_KEY / SECRET_KEY / JWT_SECRET_KEY are NOT included in the
backup on purpose — they must be migrated separately via docker/.env.
"""
import gzip
import io
import json
import os
import struct
import subprocess
import tempfile
import base64
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

MAGIC = b'MNTRBAK1'
SALT_LEN = 32
PBKDF2_ITERATIONS = 480000  # OWASP-recommended minimum for PBKDF2-HMAC-SHA256
DUMP_TIMEOUT = 600           # seconds — enough for large databases
RESTORE_TIMEOUT = 600
# Max decompressed SQL size (default 500 MB). Prevents zip-bomb / DoS against
# the single gunicorn worker. Raise MAX_RESTORE_SQL_MB in docker/.env if needed.
MAX_DECOMPRESSED_BYTES = int(os.environ.get('MAX_RESTORE_SQL_MB', '500')) * 1024 * 1024


# ── Crypto helpers ────────────────────────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a Fernet-compatible 32-byte key from *password* and *salt*."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))


# ── Safe gzip decompression ───────────────────────────────────────────────────

def _safe_gunzip(compressed: bytes, limit: int | None = None) -> bytes:
    """Decompress *compressed* in 1 MB chunks, aborting if output exceeds *limit*.

    Prevents zip-bomb / DoS: a 15 MB .mntrbak with gzip ratio ~1000:1 could
    otherwise expand to gigabytes and OOM the single gunicorn worker.

    Reads MAX_DECOMPRESSED_BYTES at call time (not import time) so the env var
    and the constant can be patched in tests.
    """
    if limit is None:
        limit = MAX_DECOMPRESSED_BYTES
    out = bytearray()
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as gz:
        while True:
            chunk = gz.read(1024 * 1024)
            if not chunk:
                break
            out += chunk
            if len(out) > limit:
                raise ValueError(
                    f'El respaldo descomprimido supera el límite de '
                    f'{limit // (1024 * 1024)} MB. '
                    'Aumenta MAX_RESTORE_SQL_MB en docker/.env si es necesario.'
                )
    return bytes(out)


# ── mysqldump / mysql ─────────────────────────────────────────────────────────

def _save_safety_snapshot() -> str | None:
    """Dump the current DB to a temp file immediately before a restore.

    Returns the absolute path of the gzip-compressed snapshot on success, or
    None if the dump fails (restore still proceeds but the caller should log a
    warning).  The file is created with permissions 0o600 (owner read/write only).
    """
    try:
        sql = dump_database()
        compressed = gzip.compress(sql, compresslevel=6)
        ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        fd, path = tempfile.mkstemp(
            suffix='.sql.gz',
            prefix=f'monetra-pre-restore-{ts}-',
        )
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(compressed)
            os.chmod(path, 0o600)
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        return path
    except Exception:
        return None


def dump_database() -> bytes:
    """Run mysqldump and return the raw SQL bytes.

    The DB password is passed via the MYSQL_PWD environment variable so it
    never appears in the process argument list (prevents leakage via /proc).
    """
    env = os.environ.copy()
    env['MYSQL_PWD'] = os.environ.get('DB_PASSWORD', '')

    cmd = [
        'mysqldump',
        '--single-transaction',
        '--quick',
        '--routines',
        '--triggers',
        '--add-drop-table',
        '--default-character-set=utf8mb4',
        f'-h{os.environ.get("DB_HOST", "mysql")}',
        f'-P{os.environ.get("DB_PORT", "3306")}',
        f'-u{os.environ.get("DB_USER", "")}',
        os.environ.get('DB_NAME', ''),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        env=env,
        shell=False,
        timeout=DUMP_TIMEOUT,
    )

    if result.returncode != 0:
        err = result.stderr.decode('utf-8', errors='replace')
        raise RuntimeError(f'mysqldump falló (código {result.returncode}): {err[:500]}')

    return result.stdout


def restore_database(sql_bytes: bytes) -> None:
    """Feed *sql_bytes* to the mysql client to replace the entire database.

    Same MYSQL_PWD trick as dump_database.
    """
    env = os.environ.copy()
    env['MYSQL_PWD'] = os.environ.get('DB_PASSWORD', '')

    cmd = [
        'mysql',
        f'-h{os.environ.get("DB_HOST", "mysql")}',
        f'-P{os.environ.get("DB_PORT", "3306")}',
        f'-u{os.environ.get("DB_USER", "")}',
        os.environ.get('DB_NAME', ''),
    ]

    result = subprocess.run(
        cmd,
        input=sql_bytes,
        capture_output=True,
        env=env,
        shell=False,
        timeout=RESTORE_TIMEOUT,
    )

    if result.returncode != 0:
        err = result.stderr.decode('utf-8', errors='replace')
        raise RuntimeError(f'mysql restore falló (código {result.returncode}): {err[:500]}')


# ── High-level backup / restore ───────────────────────────────────────────────

def make_backup(password: str) -> bytes:
    """Create a full encrypted backup blob.

    Raises RuntimeError if mysqldump fails.
    Raises ValueError if *password* is empty.
    """
    if not password:
        raise ValueError('La contraseña del respaldo no puede estar vacía.')

    sql_bytes = dump_database()
    compressed = gzip.compress(sql_bytes, compresslevel=6)

    manifest = {
        'format': 'monetra-backup/1',
        'db_name': os.environ.get('DB_NAME', ''),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'app_version': '2.6',
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode('utf-8')
    header = struct.pack('>I', len(manifest_bytes)) + manifest_bytes

    plaintext = header + compressed

    salt = os.urandom(SALT_LEN)
    key = _derive_key(password, salt)
    token = Fernet(key).encrypt(plaintext)

    return MAGIC + salt + token


def read_backup(blob: bytes, password: str) -> bytes:
    """Decrypt and validate a backup blob.

    Returns the raw SQL bytes ready to feed to restore_database().

    Raises:
        ValueError — bad magic, wrong password, corrupted data, DB name mismatch.
    """
    if not blob.startswith(MAGIC):
        raise ValueError(
            'El archivo no es un respaldo válido de Monetra '
            '(cabecera inválida).'
        )

    pos = len(MAGIC)
    salt = blob[pos:pos + SALT_LEN]
    if len(salt) < SALT_LEN:
        raise ValueError('Archivo de respaldo corrupto o truncado.')
    pos += SALT_LEN

    token = blob[pos:]
    key = _derive_key(password, salt)

    try:
        plaintext = Fernet(key).decrypt(token)
    except InvalidToken:
        raise ValueError(
            'Contraseña de respaldo incorrecta o el archivo fue alterado.'
        )

    if len(plaintext) < 4:
        raise ValueError('Payload del respaldo demasiado corto.')

    manifest_len = struct.unpack('>I', plaintext[:4])[0]
    if 4 + manifest_len > len(plaintext):
        raise ValueError('Manifiesto del respaldo corrupto.')

    manifest_bytes = plaintext[4:4 + manifest_len]
    compressed = plaintext[4 + manifest_len:]

    try:
        manifest = json.loads(manifest_bytes.decode('utf-8'))
    except Exception:
        raise ValueError('Manifiesto del respaldo inválido (no es JSON).')

    if manifest.get('format') != 'monetra-backup/1':
        raise ValueError(
            f"Formato de respaldo no reconocido: '{manifest.get('format')}'."
        )

    expected_db = os.environ.get('DB_NAME', '')
    backup_db = manifest.get('db_name', '')
    # H9: strict check — empty db_name in manifest is also rejected when the
    # server knows its expected DB_NAME, preventing accidental cross-DB restores.
    if expected_db and backup_db != expected_db:
        raise ValueError(
            f"Este respaldo pertenece a la base de datos '{backup_db or '(sin nombre)'}', "
            f"pero el servidor usa '{expected_db}'. "
            "Verifica que estás restaurando en el servidor correcto."
        )

    try:
        sql_bytes = _safe_gunzip(compressed)
    except ValueError:
        raise
    except Exception:
        raise ValueError('Los datos SQL del respaldo están corruptos.')

    return sql_bytes
