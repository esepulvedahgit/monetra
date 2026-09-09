"""Safe staging and cryptographic verification for Android release APKs."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


class ReleaseValidationError(ValueError):
    """An upload failed validation; messages are intentionally safe for users."""


def _normalise_fingerprint(value: str) -> str:
    return re.sub(r'[^0-9A-Fa-f]', '', value or '').upper()


def current_apk_path(releases_dir: str | os.PathLike[str]) -> Path:
    return Path(releases_dir) / 'monetra-current.apk'


def verify_apk_signature(apk_path: str | os.PathLike[str]) -> str:
    """Return the signer SHA-256 fingerprint after ``apksigner`` validates APK.

    ``apksigner verify`` checks APK Signature Scheme integrity.  Its certificate
    fingerprint output is parsed rather than trusting an upload-supplied value.
    """
    try:
        result = subprocess.run(
            ['apksigner', 'verify', '--print-certs', str(apk_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise ReleaseValidationError('El verificador de firmas APK no está disponible.') from exc
    except subprocess.TimeoutExpired as exc:
        raise ReleaseValidationError('La verificación de firma excedió el tiempo permitido.') from exc

    if result.returncode != 0:
        raise ReleaseValidationError('El APK no tiene una firma válida.')

    match = re.search(
        r'Signer\s+#1\s+certificate\s+SHA-256\s+digest:\s*([^\r\n]+)',
        result.stdout,
        re.IGNORECASE,
    )
    fingerprint = _normalise_fingerprint(match.group(1) if match else '')
    if not re.fullmatch(r'[0-9A-F]{64}', fingerprint):
        raise ReleaseValidationError('No se pudo obtener el certificado de firma del APK.')
    return fingerprint


def stage_apk(upload, releases_dir: str | os.PathLike[str], max_bytes: int, expected_fingerprint: str):
    """Stream, structurally validate and signature-check an upload into a temp file.

    The caller owns the returned file and must atomically replace it into the
    current release only after database metadata has been prepared.
    """
    filename = (getattr(upload, 'filename', '') or '').strip()
    if Path(filename).suffix.lower() != '.apk':
        raise ReleaseValidationError('Debes seleccionar un archivo APK (.apk).')
    if not expected_fingerprint:
        raise ReleaseValidationError('La huella del certificado APK no está configurada.')

    expected = _normalise_fingerprint(expected_fingerprint)
    if not re.fullmatch(r'[0-9A-F]{64}', expected):
        raise ReleaseValidationError('La huella del certificado APK configurada no es válida.')

    directory = Path(releases_dir)
    directory.mkdir(mode=0o750, parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.upload-', suffix='.apk', dir=directory)
    staged = Path(name)
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(descriptor, 'wb') as destination:
            while True:
                chunk = upload.stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ReleaseValidationError('El APK supera el tamaño máximo permitido.')
                digest.update(chunk)
                destination.write(chunk)
        os.chmod(staged, 0o600)

        if total == 0 or not zipfile.is_zipfile(staged):
            raise ReleaseValidationError('El archivo no es un APK válido.')
        with zipfile.ZipFile(staged) as archive:
            if 'AndroidManifest.xml' not in archive.namelist():
                raise ReleaseValidationError('El archivo no es un APK válido.')

        certificate = verify_apk_signature(staged)
        if certificate != expected:
            raise ReleaseValidationError('El APK no fue firmado con el certificado autorizado.')
        return staged, digest.hexdigest(), total, certificate
    except Exception:
        staged.unlink(missing_ok=True)
        raise
