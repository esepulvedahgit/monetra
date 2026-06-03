"""AI provider adapters for receipt extraction.

Supported providers and their API formats:
  openai      → OpenAI-compatible (https://api.openai.com/v1)
  deepseek    → OpenAI-compatible (https://api.deepseek.com)
  openrouter  → OpenAI-compatible (https://openrouter.ai/api/v1)
  anthropic   → Anthropic Messages API
  gemini      → Google Gemini generateContent
"""

import base64
import json

import requests

from app.email_service import decrypt_ai_token
from app.scanner.prompt import RECEIPT_SYSTEM_PROMPT

DEFAULT_BASE_URLS = {
    'openai':     'https://api.openai.com/v1',
    'deepseek':   'https://api.deepseek.com',
    'openrouter': 'https://openrouter.ai/api/v1',
}

_OPENAI_COMPATIBLE = {'openai', 'deepseek', 'openrouter'}


def _parse_json_response(text: str) -> dict:
    """Parse JSON string, raising ValueError on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("La respuesta de la IA no es JSON válido.")


def _check_http_error(response: requests.Response) -> None:
    """Raise ValueError if response status is not 200."""
    if response.status_code != 200:
        try:
            body = response.text[:200]
        except Exception:
            body = str(response.status_code)
        raise ValueError(
            f"Error del proveedor de IA: {response.status_code} — {body}"
        )


def _call_openai_compatible(config, b64_image: str, mime_type: str, token: str) -> dict:
    base_url = config.base_url or DEFAULT_BASE_URLS.get(config.provider, DEFAULT_BASE_URLS['openai'])
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
        "max_tokens": 1024,
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
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
        "max_tokens": 1024,
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
        resp = requests.post(url, headers=headers, json=body, timeout=30)
    except requests.Timeout:
        raise ValueError("Tiempo de espera agotado al contactar al proveedor de IA.")

    _check_http_error(resp)
    try:
        content = resp.json()["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("Respuesta inesperada del proveedor Anthropic.")
    return _parse_json_response(content)


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
            "maxOutputTokens": 1024,
        },
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
    except requests.Timeout:
        raise ValueError("Tiempo de espera agotado al contactar al proveedor de IA.")

    _check_http_error(resp)
    try:
        content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("Respuesta inesperada del proveedor Gemini.")
    return _parse_json_response(content)


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
