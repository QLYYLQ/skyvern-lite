"""Shared test fixtures."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from skyvern_lite._http import AsyncHttpClient, SyncHttpClient
from skyvern_lite.sessions import AsyncSessionsResource, SessionsResource


class FakeSyncHttp:
    """Fake sync HTTP client for testing."""

    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses: dict[str, Any] = responses or {}
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((method, path, json))
        key = f"{method} {path}"
        response = self.responses.get(key, {})
        if callable(response):
            return response()
        if isinstance(response, Exception):
            raise response
        return response


class FakeAsyncHttp:
    """Fake async HTTP client for testing."""

    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses: dict[str, Any] = responses or {}
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((method, path, json))
        key = f"{method} {path}"
        response = self.responses.get(key, {})
        if callable(response):
            return response()
        if isinstance(response, Exception):
            raise response
        return response


SAMPLE_SESSION_RESPONSE = {
    "browser_session_id": "sess-123",
    "browser_address": "wss://browser.skyvern.com/devtools/browser/abc",
    "status": "running",
    "created_at": "2026-01-15T10:00:00Z",
    "app_url": "https://app.skyvern.com/sessions/sess-123",
}


@pytest.fixture
def sample_response() -> dict[str, Any]:
    return dict(SAMPLE_SESSION_RESPONSE)


@pytest.fixture
def fake_sync_http() -> FakeSyncHttp:
    return FakeSyncHttp()


@pytest.fixture
def fake_async_http() -> FakeAsyncHttp:
    return FakeAsyncHttp()


@pytest.fixture
def sync_sessions(fake_sync_http: FakeSyncHttp) -> SessionsResource:
    return SessionsResource(fake_sync_http)


@pytest.fixture
def async_sessions(fake_async_http: FakeAsyncHttp) -> AsyncSessionsResource:
    return AsyncSessionsResource(fake_async_http)
