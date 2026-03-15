"""Tests for session CRUD resources."""

from __future__ import annotations

from typing import Any

import pytest

from skyvern_lite.exceptions import SessionNotFoundError, TimeoutError
from skyvern_lite.models import ManagedProxyConfig, ProxyConfig
from skyvern_lite.sessions import SessionsResource, _build_create_body, _to_session_info

from .conftest import SAMPLE_SESSION_RESPONSE, FakeAsyncHttp, FakeSyncHttp


class TestToSessionInfo:
    def test_maps_fields(self):
        info = _to_session_info(SAMPLE_SESSION_RESPONSE)
        assert info.session_id == "sess-123"
        assert info.cdp_url == "wss://browser.skyvern.com/devtools/browser/abc"
        assert info.status == "active"  # "running" → "active"
        assert info.inspect_url == "https://app.skyvern.com/sessions/sess-123"

    def test_extra_fields_in_metadata(self):
        data = {**SAMPLE_SESSION_RESPONSE, "proxy_location": "RESIDENTIAL"}
        info = _to_session_info(data)
        assert info.metadata["proxy_location"] == "RESIDENTIAL"

    def test_delete_fn_attached(self):
        called = False

        def _delete():
            nonlocal called
            called = True

        info = _to_session_info(SAMPLE_SESSION_RESPONSE, delete_fn=_delete)
        info.__exit__(None, None, None)
        assert called


class TestBuildCreateBody:
    def test_empty_body(self):
        body = _build_create_body("normal", None, None, None, None, {})
        assert body == {}

    def test_managed_proxy(self):
        proxy = ManagedProxyConfig(country="US")
        body = _build_create_body("normal", proxy, None, None, None, {})
        assert body["proxy_location"] == "RESIDENTIAL"

    def test_managed_proxy_unsupported_country(self):
        proxy = ManagedProxyConfig(country="XX")
        with pytest.raises(ValueError, match="Unsupported proxy country"):
            _build_create_body("normal", proxy, None, None, None, {})

    def test_custom_proxy_raises(self):
        proxy = ProxyConfig(server="http://proxy:8080")
        with pytest.raises(NotImplementedError, match="custom proxy"):
            _build_create_body("normal", proxy, None, None, None, {})

    def test_vendor_params_passthrough(self):
        body = _build_create_body(
            "normal", None, None, None, None,
            {"timeout": 120, "browser_type": "chromium", "unknown_param": "x"},
        )
        assert body["timeout"] == 120
        assert body["browser_type"] == "chromium"
        assert "unknown_param" not in body


class TestSessionsResourceCreate:
    def test_create_returns_session_info(self, sample_response: dict[str, Any]):
        http = FakeSyncHttp(responses={
            "POST /v1/browser_sessions": sample_response,
        })
        sessions = SessionsResource(http)
        info = sessions.create()
        assert info.session_id == "sess-123"
        assert info.cdp_url == "wss://browser.skyvern.com/devtools/browser/abc"
        assert info.status == "active"

    def test_create_polls_when_no_cdp_url(self, sample_response: dict[str, Any]):
        no_cdp = {**sample_response, "browser_address": None}
        call_count = 0

        def _get_response():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                return sample_response
            return no_cdp

        http = FakeSyncHttp(responses={
            "POST /v1/browser_sessions": no_cdp,
            "GET /v1/browser_sessions/sess-123": _get_response,
        })
        sessions = SessionsResource(http)

        import unittest.mock
        with unittest.mock.patch("skyvern_lite.sessions.time.sleep"):
            info = sessions.create()

        assert info.cdp_url == "wss://browser.skyvern.com/devtools/browser/abc"

    def test_create_context_manager(self, sample_response: dict[str, Any]):
        http = FakeSyncHttp(responses={
            "POST /v1/browser_sessions": sample_response,
            "POST /v1/browser_sessions/sess-123/close": {},
        })
        sessions = SessionsResource(http)

        with sessions.create() as session:
            assert session.session_id == "sess-123"

        # Verify delete was called
        delete_calls = [c for c in http.calls if "close" in c[1]]
        assert len(delete_calls) == 1


class TestSessionsResourceGet:
    def test_get(self, sample_response: dict[str, Any]):
        http = FakeSyncHttp(responses={
            "GET /v1/browser_sessions/sess-123": sample_response,
        })
        sessions = SessionsResource(http)
        info = sessions.get("sess-123")
        assert info.session_id == "sess-123"


class TestSessionsResourceList:
    def test_list_array_response(self, sample_response: dict[str, Any]):
        http = FakeSyncHttp(responses={
            "GET /v1/browser_sessions": [sample_response, sample_response],
        })
        sessions = SessionsResource(http)
        result = sessions.list()
        assert len(result) == 2
        assert all(s.session_id == "sess-123" for s in result)

    def test_list_wrapped_response(self, sample_response: dict[str, Any]):
        http = FakeSyncHttp(responses={
            "GET /v1/browser_sessions": {
                "browser_sessions": [sample_response],
            },
        })
        sessions = SessionsResource(http)
        result = sessions.list()
        assert len(result) == 1


class TestSessionsResourceDelete:
    def test_delete_success(self):
        http = FakeSyncHttp(responses={
            "POST /v1/browser_sessions/sess-123/close": {},
        })
        sessions = SessionsResource(http)
        sessions.delete("sess-123")  # should not raise

    def test_delete_idempotent_on_404(self):
        http = FakeSyncHttp(responses={
            "POST /v1/browser_sessions/sess-123/close": SessionNotFoundError("not found"),
        })
        sessions = SessionsResource(http)
        sessions.delete("sess-123")  # should not raise


class TestAsyncSessionsResource:
    @pytest.mark.asyncio
    async def test_create(self, sample_response: dict[str, Any]):
        from skyvern_lite.sessions import AsyncSessionsResource

        http = FakeAsyncHttp(responses={
            "POST /v1/browser_sessions": sample_response,
        })
        sessions = AsyncSessionsResource(http)
        info = await sessions.create()
        assert info.session_id == "sess-123"

    @pytest.mark.asyncio
    async def test_get(self, sample_response: dict[str, Any]):
        from skyvern_lite.sessions import AsyncSessionsResource

        http = FakeAsyncHttp(responses={
            "GET /v1/browser_sessions/sess-123": sample_response,
        })
        sessions = AsyncSessionsResource(http)
        info = await sessions.get("sess-123")
        assert info.session_id == "sess-123"

    @pytest.mark.asyncio
    async def test_delete_idempotent(self):
        from skyvern_lite.sessions import AsyncSessionsResource

        http = FakeAsyncHttp(responses={
            "POST /v1/browser_sessions/sess-123/close": SessionNotFoundError("gone"),
        })
        sessions = AsyncSessionsResource(http)
        await sessions.delete("sess-123")  # should not raise

    @pytest.mark.asyncio
    async def test_list(self, sample_response: dict[str, Any]):
        from skyvern_lite.sessions import AsyncSessionsResource

        http = FakeAsyncHttp(responses={
            "GET /v1/browser_sessions": [sample_response],
        })
        sessions = AsyncSessionsResource(http)
        result = await sessions.list()
        assert len(result) == 1
