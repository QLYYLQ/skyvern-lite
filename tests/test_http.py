"""Tests for internal HTTP client wrappers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from skyvern_lite._http import (
    SyncHttpClient,
    _parse_retry_after,
    _raise_for_status,
)
from skyvern_lite.exceptions import (
    AuthenticationError,
    CloudBrowserError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
    TimeoutError,
)


def _make_response(
    status_code: int,
    json_body: dict | None = None,
    headers: dict[str, str] | None = None,
    text: str = "",
) -> httpx.Response:
    """Create a mock httpx.Response."""
    kwargs: dict[str, object] = {
        "status_code": status_code,
        "headers": headers or {},
        "request": httpx.Request("GET", "https://test.com"),
    }
    if json_body is not None:
        kwargs["json"] = json_body
    elif text:
        kwargs["text"] = text
    return httpx.Response(**kwargs)  # type: ignore[arg-type]


class TestParseRetryAfter:
    def test_present(self):
        resp = _make_response(429, headers={"retry-after": "30"})
        assert _parse_retry_after(resp) == 30.0

    def test_absent(self):
        resp = _make_response(200)
        assert _parse_retry_after(resp) is None

    def test_invalid(self):
        resp = _make_response(429, headers={"retry-after": "not-a-number"})
        assert _parse_retry_after(resp) is None


class TestRaiseForStatus:
    def test_success_does_not_raise(self):
        resp = _make_response(200)
        _raise_for_status(resp)  # should not raise

    def test_401_raises_auth_error(self):
        resp = _make_response(401, json_body={"detail": "Invalid API key"})
        with pytest.raises(AuthenticationError, match="Invalid API key"):
            _raise_for_status(resp)

    def test_403_raises_auth_error(self):
        resp = _make_response(403, json_body={"message": "Forbidden"})
        with pytest.raises(AuthenticationError, match="Forbidden"):
            _raise_for_status(resp)

    def test_404_raises_session_not_found(self):
        resp = _make_response(404, json_body={"detail": "Not found"})
        with pytest.raises(SessionNotFoundError):
            _raise_for_status(resp)

    def test_429_raises_quota_exceeded(self):
        resp = _make_response(
            429,
            json_body={"detail": "Rate limited"},
            headers={"retry-after": "60"},
        )
        with pytest.raises(QuotaExceededError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.retry_after == 60

    def test_500_raises_provider_error(self):
        resp = _make_response(
            500,
            json_body={"detail": "Internal error"},
            headers={"x-request-id": "req-xyz"},
        )
        with pytest.raises(ProviderError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.status_code == 500
        assert exc_info.value.request_id == "req-xyz"

    def test_502_raises_provider_error(self):
        resp = _make_response(502, text="Bad Gateway")
        with pytest.raises(ProviderError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.status_code == 502

    def test_422_raises_generic(self):
        resp = _make_response(422, json_body={"detail": "Validation error"})
        with pytest.raises(CloudBrowserError, match="422"):
            _raise_for_status(resp)


class TestSyncHttpClient:
    def test_successful_request(self):
        client = SyncHttpClient(
            base_url="https://api.test.com",
            api_key="test-key",
            max_retries=0,
        )
        mock_response = _make_response(200, json_body={"ok": True})
        with patch.object(client._client, "request", return_value=mock_response):
            result = client.request("GET", "/test")
        assert result == {"ok": True}
        client.close()

    def test_retries_on_500(self):
        client = SyncHttpClient(
            base_url="https://api.test.com",
            api_key="test-key",
            max_retries=1,
        )
        fail_resp = _make_response(500, json_body={"detail": "error"})
        ok_resp = _make_response(200, json_body={"ok": True})

        with patch.object(
            client._client,
            "request",
            side_effect=[fail_resp, ok_resp],
        ), patch("skyvern_lite._http.time.sleep"):
            result = client.request("GET", "/test")

        assert result == {"ok": True}
        client.close()

    def test_timeout_exception(self):
        client = SyncHttpClient(
            base_url="https://api.test.com",
            api_key="test-key",
            max_retries=0,
        )
        with patch.object(
            client._client,
            "request",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(TimeoutError, match="timed out"):
                client.request("GET", "/test")
        client.close()

    def test_connect_error(self):
        client = SyncHttpClient(
            base_url="https://api.test.com",
            api_key="test-key",
            max_retries=0,
        )
        with patch.object(
            client._client,
            "request",
            side_effect=httpx.ConnectError("connection refused"),
        ):
            with pytest.raises(NetworkError, match="connection refused"):
                client.request("GET", "/test")
        client.close()

    def test_204_returns_empty_dict(self):
        client = SyncHttpClient(
            base_url="https://api.test.com",
            api_key="test-key",
            max_retries=0,
        )
        mock_response = _make_response(204)
        with patch.object(client._client, "request", return_value=mock_response):
            result = client.request("POST", "/close")
        assert result == {}
        client.close()

    def test_retries_on_429_with_retry_after(self):
        client = SyncHttpClient(
            base_url="https://api.test.com",
            api_key="test-key",
            max_retries=1,
        )
        fail_resp = _make_response(
            429,
            json_body={"detail": "rate limited"},
            headers={"retry-after": "1"},
        )
        ok_resp = _make_response(200, json_body={"ok": True})

        with patch.object(
            client._client,
            "request",
            side_effect=[fail_resp, ok_resp],
        ), patch("skyvern_lite._http.time.sleep") as mock_sleep:
            result = client.request("GET", "/test")

        assert result == {"ok": True}
        mock_sleep.assert_called_once_with(1.0)
        client.close()

    def test_retries_timeout_exception_then_succeeds(self):
        client = SyncHttpClient(
            base_url="https://api.test.com",
            api_key="test-key",
            max_retries=1,
        )
        ok_resp = _make_response(200, json_body={"ok": True})

        with patch.object(
            client._client,
            "request",
            side_effect=[httpx.TimeoutException("timeout"), ok_resp],
        ), patch("skyvern_lite._http.time.sleep"):
            result = client.request("GET", "/test")

        assert result == {"ok": True}
        client.close()
