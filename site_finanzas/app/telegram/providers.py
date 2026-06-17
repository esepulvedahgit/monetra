"""AI provider adapters for receipt extraction.

Supported providers and their API formats:
  openai      → OpenAI-compatible (https://api.openai.com/v1)
  deepseek    → OpenAI-compatible (https://api.deepseek.com)
  openrouter  → OpenAI-compatible (https://openrouter.ai/api/v1)
  anthropic   → Anthropic Messages API
  gemini      → Google Gemini generateContent
"""

import base64
import ipaddress
import json
import logging
import re
import socket
from urllib.parse import urlparse

import requests

_logger = logging.getLogger(__name__)

from app.email_service import decrypt_ai_token
from app.telegram.prompt import RECEIPT_SYSTEM_PROMPT

DEFAULT_BASE_URLS = {
    'openai':     'https://api.openai.com/v1',
    'deepseek':   'https://api.deepseek.com',
    'openrouter': 'https://openrouter.ai/api/v1',
}

_OPENAI_COMPATIBLE = {'openai', 'deepseek', 'openrouter'}

_BLOCKED_HOSTNAMES = frozenset({
    'localhost', '0.0.0.0', '::1', '[::1]', 'metadata.google.internal',
})
_BLOCKED_HOSTNAME_SUFFIXES = ('.local', '.internal', '.localhost')


def _validate_base_url(base_url: str) -> None:
    """Raise ValueError if base_url could target private/internal infrastructure (SSRF)."""
    try:
        parsed = urlparse(base_url)
    except Exception:
        raise ValueError("URL base inválida.")

    if parsed.scheme not in ('http', 'https'):
        raise ValueError("URL base debe usar http o https.")

    hostname = (parsed.hostname or '').lower().rstrip('.')
    if not hostname:
        raise ValueError("URL base inválida: sin hostname.")

    if hostname in _BLOCKED_HOSTNAMES:
        raise ValueError("URL base no permitida.")

    for suffix in _BLOCKED_HOSTNAME_SUFFIXES:
        if hostname.endswith(suffix):
            raise ValueError("URL base no permitida.")

    # Check literal IP first.
    # Strip IPv6 zone ID (e.g. "fe80::1%25eth0" → "fe80::1") before parsing —
    # ipaddress.ip_address() raises ValueError on zone IDs, which would silently
    # fall through to the DNS block and bypass the private-range check.
    try:
        addr = ipaddress.ip_address(hostname.split('%')[0])
        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved or addr.is_unspecified:
            raise ValueError("URL base no permitida.")
    except ValueError as exc:
        if "no permitida" in str(exc):
            raise
        # hostname is not an IP literal — fall through to DNS check

    # Resolve hostname and reject if ANY returned address is in a blocked range.
    # DNS failures are non-blocking (the outbound request will fail naturally).
    try:
        for _family, _type, _proto, _canon, sockaddr in socket.getaddrinfo(hostname, None):
            try:
                resolved = ipaddress.ip_address(sockaddr[0])
                if (resolved.is_loopback or resolved.is_private or resolved.is_link_local
                        or resolved.is_reserved or resolved.is_unspecified):
                    raise ValueError("URL base no permitida.")
            except ValueError as exc:
                if "no permitida" in str(exc):
                    raise
    except ValueError:
        raise
    except Exception:
        pass  # DNS unavailable — let the outbound HTTP request fail naturally


def _parse_json_response(text: str) -> dict:
    """Parse JSON from an LLM response, tolerating markdown fences and surrounding prose."""
    if not text:
        raise ValueError("No se pudo leer el recibo. Asegúrate de que la imagen sea clara y vuelve a intentarlo.")

    # 1. Try direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Strip markdown code fences (```json ... ``` or ``` ... ```)
    stripped = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        pass

    # 3. Extract the first {...} block from mixed text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass

    preview = text[:120] if text else "(vacía)"
    raise ValueError(
        f"No se pudo leer el recibo. Asegúrate de que la imagen sea clara y vuelve a intentarlo. "
        f"[modelo devolvió: {preview!r}]"
    )


_VISION_UNSUPPORTED_SIGNALS = (
    'image_url', 'unknown variant', 'does not support image',
    'vision', 'multimodal', 'image input',
)

_VISION_ERROR_MSG = (
    "El modelo seleccionado no admite imágenes. "
    "Cambia a un modelo multimodal (gpt-4o, claude-3-5-sonnet, gemini-1.5-flash)."
)


def _check_http_error(response: requests.Response) -> None:
    """Raise ValueError if response status is not 200."""
    if response.status_code != 200:
        try:
            body = response.text[:400]
        except Exception:
            body = str(response.status_code)
        body_lower = body.lower()
        if any(s in body_lower for s in _VISION_UNSUPPORTED_SIGNALS):
            raise ValueError(_VISION_ERROR_MSG)
        # Log full body server-side only — never expose provider internals to the client.
        _logger.warning("AI provider error %s: %s", response.status_code, body)
        raise ValueError(
            f"Error del proveedor de IA: {response.status_code}"
        )


def _call_openai_compatible(config, b64_image: str, mime_type: str, token: str) -> dict:
    base_url = config.base_url or DEFAULT_BASE_URLS.get(config.provider, DEFAULT_BASE_URLS['openai'])
    if config.base_url:
        _validate_base_url(config.base_url)
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": RECEIPT_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}},
                {"type": "text", "text": "Extract receipt data as JSON."},
            ]},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 2048,
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30, allow_redirects=False)
    except requests.Timeout:
        raise ValueError("Tiempo de espera agotado al contactar al proveedor de IA.")

    _check_http_error(resp)
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("Respuesta inesperada del proveedor OpenAI-compatible.")
    return _parse_json_response(content)


def _call_anthropic(config, b64_image: str, mime_type: str, token: str) -> dict:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": token,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": config.model,
        "max_tokens": 2048,
        "system": RECEIPT_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": b64_image,
                    },
                },
                {"type": "text", "text": "Extract receipt data as JSON."},
            ]},
        ],
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30, allow_redirects=False)
    except requests.Timeout:
        raise ValueError("Tiempo de espera agotado al contactar al proveedor de IA.")

    _check_http_error(resp)
    try:
        content = resp.json()["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("Respuesta inesperada del proveedor Anthropic.")
    return _parse_json_response(content)


_GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "total":    {"type": "NUMBER",  "nullable": True},
        "currency": {"type": "STRING",  "nullable": True},
        "merchant": {"type": "STRING",  "nullable": True},
        "date":     {"type": "STRING",  "nullable": True},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name":       {"type": "STRING"},
                    "qty":        {"type": "NUMBER", "nullable": True},
                    "unit_price": {"type": "NUMBER", "nullable": True},
                    "line_total":  {"type": "NUMBER", "nullable": True},
                },
            },
        },
        "error": {"type": "STRING", "nullable": True},
    },
}


def _call_gemini(config, b64_image: str, mime_type: str, token: str) -> dict:
    model_name = config.model or "gemini-1.5-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent?key={token}"
    )
    headers = {"Content-Type": "application/json"}
    body = {
        "system_instruction": {"parts": [{"text": RECEIPT_SYSTEM_PROMPT}]},
        "contents": [{"parts": [
            {"inline_data": {"mime_type": mime_type, "data": b64_image}},
            {"text": "Extract receipt data as JSON."},
        ]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "responseSchema": _GEMINI_RESPONSE_SCHEMA,
            "maxOutputTokens": 2048,
        },
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30, allow_redirects=False)
    except requests.Timeout:
        raise ValueError("Tiempo de espera agotado al contactar al proveedor de IA.")

    _check_http_error(resp)

    resp_json = resp.json()
    candidate = (resp_json.get("candidates") or [{}])[0]
    finish_reason = candidate.get("finishReason", "STOP")

    if finish_reason == "MAX_TOKENS":
        raise ValueError(
            "El recibo tiene demasiados ítems para procesar de una vez. "
            "Intenta con una sección más pequeña del recibo."
        )
    if finish_reason == "SAFETY":
        raise ValueError(
            "El modelo bloqueó la imagen por filtros de seguridad. "
            "Asegúrate de que la imagen sea un recibo o factura."
        )
    if finish_reason not in ("STOP", "MODEL_LENGTH", ""):
        raise ValueError(
            f"El modelo no completó la respuesta (finishReason: {finish_reason}). Intenta nuevamente."
        )

    try:
        content = candidate["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("Respuesta inesperada del proveedor Gemini.")
    return _parse_json_response(content)


def test_connection(provider: str, model: str, base_url: str, token: str) -> None:
    """Make a lightweight text-only call to verify provider credentials and model.

    Raises ValueError with a human-readable message on any failure.
    """
    if not token:
        raise ValueError("Token de API no configurado o inválido.")

    provider = (provider or '').lower()

    if base_url:
        _validate_base_url(base_url)

    if provider in _OPENAI_COMPATIBLE:
        _url = f"{(base_url or DEFAULT_BASE_URLS.get(provider, DEFAULT_BASE_URLS['openai'])).rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": [{"role": "user", "content": "Responde OK"}],
            "max_tokens": 5,
        }
        try:
            resp = requests.post(_url, headers=headers, json=body, timeout=15, allow_redirects=False)
        except requests.Timeout:
            raise ValueError("Tiempo de espera agotado al contactar al proveedor de IA.")
        _check_http_error(resp)

    elif provider == 'anthropic':
        headers = {
            "x-api-key": token,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "Responde OK"}],
        }
        try:
            resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=15, allow_redirects=False)
        except requests.Timeout:
            raise ValueError("Tiempo de espera agotado al contactar al proveedor de IA.")
        _check_http_error(resp)

    elif provider == 'gemini':
        _model = model or "gemini-1.5-flash"
        _url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{_model}:generateContent?key={token}"
        )
        body = {"contents": [{"parts": [{"text": "Responde OK"}]}], "generationConfig": {"maxOutputTokens": 5}}
        try:
            resp = requests.post(_url, headers={"Content-Type": "application/json"}, json=body, timeout=15, allow_redirects=False)
        except requests.Timeout:
            raise ValueError("Tiempo de espera agotado al contactar al proveedor de IA.")
        _check_http_error(resp)

    else:
        raise ValueError(f"Proveedor desconocido: {provider}")


def extract_receipt(config, image_bytes: bytes, mime_type: str) -> dict:
    """Extract receipt data from image bytes using the configured AI provider.

    Args:
        config: UserAIConfig instance with provider, model, base_url, api_token_encrypted.
        image_bytes: Raw image bytes.
        mime_type: MIME type of the image (e.g. 'image/jpeg').

    Returns:
        Normalized dict with keys: total, currency, merchant, date, items.

    Raises:
        ValueError: Human-readable error message on any failure.
    """
    token = decrypt_ai_token(config.api_token_encrypted) if config.api_token_encrypted else ""
    if not token:
        raise ValueError("Token de API no configurado o inválido.")

    MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("La imagen es demasiado grande. Máximo 10 MB.")

    b64_image = base64.b64encode(image_bytes).decode('ascii')

    provider = (config.provider or '').lower()

    if provider in _OPENAI_COMPATIBLE:
        result = _call_openai_compatible(config, b64_image, mime_type, token)
    elif provider == 'anthropic':
        result = _call_anthropic(config, b64_image, mime_type, token)
    elif provider == 'gemini':
        result = _call_gemini(config, b64_image, mime_type, token)
    else:
        # Unknown provider — try OpenAI-compatible as a best-effort fallback
        result = _call_openai_compatible(config, b64_image, mime_type, token)

    if isinstance(result, dict) and result.get('error') == 'not_a_receipt':
        raise ValueError("La imagen no parece ser un recibo.")

    return result
