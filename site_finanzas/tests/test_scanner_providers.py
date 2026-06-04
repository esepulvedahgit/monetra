"""Tests for app/scanner/providers.py — SSRF validation, vision-error detection, test_connection."""
import json
import types
import unittest
from unittest.mock import MagicMock, patch

from app.scanner.providers import (
    _check_http_error,
    _parse_json_response,
    _validate_base_url,
    test_connection as ai_test_connection,
)


# ---------------------------------------------------------------------------
# _parse_json_response
# ---------------------------------------------------------------------------

class TestParseJsonResponse(unittest.TestCase):

    def test_clean_json(self):
        result = _parse_json_response('{"total": 12.5, "currency": "USD"}')
        self.assertEqual(result["total"], 12.5)

    def test_markdown_json_fence(self):
        text = '```json\n{"total": 9.99}\n```'
        result = _parse_json_response(text)
        self.assertEqual(result["total"], 9.99)

    def test_markdown_plain_fence(self):
        text = '```\n{"merchant": "Tienda"}\n```'
        result = _parse_json_response(text)
        self.assertEqual(result["merchant"], "Tienda")

    def test_json_embedded_in_prose(self):
        text = 'Aquí están los datos extraídos:\n{"total": 5.0, "currency": "CLP"}\nEspero que sea útil.'
        result = _parse_json_response(text)
        self.assertEqual(result["total"], 5.0)

    def test_empty_text_raises_friendly(self):
        with self.assertRaises(ValueError) as ctx:
            _parse_json_response("")
        self.assertIn("vuelve a intentarlo", str(ctx.exception))

    def test_unparseable_raises_friendly(self):
        with self.assertRaises(ValueError) as ctx:
            _parse_json_response("No puedo leer la imagen claramente.")
        self.assertIn("vuelve a intentarlo", str(ctx.exception))
        self.assertNotIn("JSON", str(ctx.exception))


# ---------------------------------------------------------------------------
# _validate_base_url
# ---------------------------------------------------------------------------

class TestValidateBaseUrl(unittest.TestCase):

    # --- blocked cases ---

    def test_localhost_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http://localhost/v1")

    def test_127_loopback_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http://127.0.0.1:8080/v1")

    def test_ipv6_loopback_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http://[::1]/v1")

    def test_rfc1918_10_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http://10.0.0.1/v1")

    def test_rfc1918_192168_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http://192.168.1.1/v1")

    def test_rfc1918_172_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http://172.16.0.1/v1")

    def test_link_local_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http://169.254.169.254/latest/meta-data/")

    def test_metadata_google_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http://metadata.google.internal/computeMetadata/v1/")

    def test_local_suffix_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http://myservice.local/v1")

    def test_internal_suffix_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http://db.internal/v1")

    def test_non_http_scheme_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("file:///etc/passwd")

    def test_ftp_scheme_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("ftp://example.com/v1")

    def test_no_hostname_blocked(self):
        with self.assertRaises(ValueError):
            _validate_base_url("http:///v1")

    # --- allowed cases ---

    def test_openai_allowed(self):
        _validate_base_url("https://api.openai.com/v1")  # must not raise

    def test_openrouter_allowed(self):
        _validate_base_url("https://openrouter.ai/api/v1")

    def test_deepseek_allowed(self):
        _validate_base_url("https://api.deepseek.com")

    def test_custom_public_host_allowed(self):
        _validate_base_url("https://my-llm-proxy.example.com/v1")

    def test_http_public_host_allowed(self):
        _validate_base_url("http://my-llm-proxy.example.com/v1")

    def test_public_ip_allowed(self):
        # Public IP — should NOT raise
        _validate_base_url("https://8.8.8.8/v1")


# ---------------------------------------------------------------------------
# _check_http_error — vision-unsupported signal detection
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, text: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


class TestCheckHttpError(unittest.TestCase):

    def test_200_no_raise(self):
        _check_http_error(_mock_response(200, "ok"))  # must not raise

    def test_401_generic_error(self):
        resp = _mock_response(401, '{"error":{"message":"Invalid API key"}}')
        with self.assertRaises(ValueError) as ctx:
            _check_http_error(resp)
        self.assertIn("401", str(ctx.exception))
        self.assertNotIn("image", str(ctx.exception))

    def test_image_url_signal_raises_actionable(self):
        body = '{"error":{"message":"unknown variant image_url, expected text at line 1"}}'
        with self.assertRaises(ValueError) as ctx:
            _check_http_error(_mock_response(400, body))
        self.assertIn("multimodal", str(ctx.exception))
        self.assertNotIn("image_url", str(ctx.exception))

    def test_vision_signal_raises_actionable(self):
        body = '{"error":"This model does not support vision"}'
        with self.assertRaises(ValueError) as ctx:
            _check_http_error(_mock_response(400, body))
        self.assertIn("multimodal", str(ctx.exception))

    def test_does_not_support_image_signal(self):
        body = "model does not support image input"
        with self.assertRaises(ValueError) as ctx:
            _check_http_error(_mock_response(400, body))
        self.assertIn("multimodal", str(ctx.exception))

    def test_unknown_400_returns_raw_truncated(self):
        body = '{"error":{"message":"some other error"}}'
        with self.assertRaises(ValueError) as ctx:
            _check_http_error(_mock_response(400, body))
        msg = str(ctx.exception)
        self.assertIn("400", msg)
        self.assertNotIn("multimodal", msg)

    def test_body_truncated_to_200_chars(self):
        long_body = "x" * 500
        with self.assertRaises(ValueError) as ctx:
            _check_http_error(_mock_response(500, long_body))
        # Error message should not exceed a reasonable length
        self.assertLessEqual(len(str(ctx.exception)), 280)


# ---------------------------------------------------------------------------
# test_connection — happy path & failures (mocked HTTP)
# ---------------------------------------------------------------------------

def _make_ok_response(body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp


class TestTestConnection(unittest.TestCase):

    def test_empty_token_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ai_test_connection("openai", "gpt-4o", "", "")
        self.assertIn("Token", str(ctx.exception))

    def test_unknown_provider_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ai_test_connection("myprovider", "some-model", "", "tok")
        self.assertIn("desconocido", str(ctx.exception))

    def test_invalid_base_url_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ai_test_connection("openai", "gpt-4o", "http://localhost/v1", "tok")
        self.assertIn("no permitida", str(ctx.exception))

    @patch("app.scanner.providers.requests.post")
    def test_openai_ok(self, mock_post):
        mock_post.return_value = _make_ok_response(
            {"choices": [{"message": {"content": "OK"}}]}
        )
        ai_test_connection("openai", "gpt-4o", "", "sk-test")
        mock_post.assert_called_once()
        url_called = mock_post.call_args[0][0]
        self.assertIn("api.openai.com", url_called)

    @patch("app.scanner.providers.requests.post")
    def test_deepseek_uses_deepseek_base_url(self, mock_post):
        mock_post.return_value = _make_ok_response(
            {"choices": [{"message": {"content": "OK"}}]}
        )
        ai_test_connection("deepseek", "deepseek-chat", "", "sk-test")
        url_called = mock_post.call_args[0][0]
        self.assertIn("deepseek.com", url_called)

    @patch("app.scanner.providers.requests.post")
    def test_openai_custom_base_url(self, mock_post):
        mock_post.return_value = _make_ok_response(
            {"choices": [{"message": {"content": "OK"}}]}
        )
        ai_test_connection("openai", "gpt-4o", "https://my-proxy.example.com/v1", "sk-test")
        url_called = mock_post.call_args[0][0]
        self.assertIn("my-proxy.example.com", url_called)

    @patch("app.scanner.providers.requests.post")
    def test_anthropic_ok(self, mock_post):
        mock_post.return_value = _make_ok_response(
            {"content": [{"text": "OK"}], "id": "msg_01"}
        )
        ai_test_connection("anthropic", "claude-3-5-sonnet-20241022", "", "sk-ant-test")
        url_called = mock_post.call_args[0][0]
        self.assertIn("anthropic.com", url_called)

    @patch("app.scanner.providers.requests.post")
    def test_gemini_ok(self, mock_post):
        mock_post.return_value = _make_ok_response(
            {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}
        )
        ai_test_connection("gemini", "gemini-1.5-flash", "", "AIza-test")
        url_called = mock_post.call_args[0][0]
        self.assertIn("generativelanguage.googleapis.com", url_called)

    @patch("app.scanner.providers.requests.post")
    def test_http_401_raises(self, mock_post):
        resp = MagicMock()
        resp.status_code = 401
        resp.text = '{"error":{"message":"Invalid API key.","type":"invalid_request_error"}}'
        mock_post.return_value = resp
        with self.assertRaises(ValueError) as ctx:
            ai_test_connection("openai", "gpt-4o", "", "bad-token")
        self.assertIn("401", str(ctx.exception))

    @patch("app.scanner.providers.requests.post")
    def test_timeout_raises_readable(self, mock_post):
        import requests as req_mod
        mock_post.side_effect = req_mod.Timeout()
        with self.assertRaises(ValueError) as ctx:
            ai_test_connection("openai", "gpt-4o", "", "sk-test")
        self.assertIn("agotado", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
