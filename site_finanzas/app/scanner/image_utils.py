import io

from flask import current_app
from flask_babel import gettext as _


_MAGIC = {
    b'\xff\xd8\xff':                   'image/jpeg',
    b'\x89PNG\r\n\x1a\n':             'image/png',
}
_ALLOWED_MIMES = frozenset({
    'image/jpeg', 'image/png', 'image/webp',
    'image/heic', 'image/heif',
})


def _detect_mime(header: bytes) -> str | None:
    """Return MIME type from first 12 bytes, or None if unrecognised."""
    if header[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp'
    if len(header) >= 12 and header[4:8] == b'ftyp':
        return 'image/heic'
    return None


def validate_and_normalize_image(image_file_or_bytes):
    """Read, validate by magic bytes, convert HEIC→JPEG if needed.

    Accepts either a file-like object (has .read()) or raw bytes.
    Returns (image_bytes: bytes, mime_type: str).
    Raises ValueError with a human-readable message on invalid input.
    """
    if hasattr(image_file_or_bytes, 'read'):
        raw = image_file_or_bytes.read()
    else:
        raw = image_file_or_bytes

    if not raw:
        raise ValueError(_('La imagen está vacía.'))

    header = raw[:12]
    detected = _detect_mime(header)

    if detected is None:
        raise ValueError(_('Formato no compatible. Usa PNG, JPG, WEBP o HEIC.'))

    try:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = 40_000_000  # ~40 MP cap against decompression bombs
        if detected in ('image/heic', 'image/heif'):
            import pillow_heif
            heif_file = pillow_heif.open_heif(raw)
            pil_img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, 'raw')
        else:
            pil_img = Image.open(io.BytesIO(raw))

        if pil_img.mode in ('RGBA', 'LA', 'P'):
            pil_img = pil_img.convert('RGB')
        elif pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')

        buf = io.BytesIO()
        pil_img.save(buf, format='JPEG', quality=92, optimize=True)
        return buf.getvalue(), 'image/jpeg'

    except Exception as exc:
        if detected in ('image/heic', 'image/heif'):
            raise ValueError(_('No se pudo procesar el archivo HEIC. Asegúrate de que no esté dañado.'))
        current_app.logger.warning('PIL normalization failed for %s, sending raw: %s', detected, exc)
        return raw, detected
