"""Tests for client classes."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from skyvern_lite import AsyncSkyvernCloud, SkyvernCloud
from skyvern_lite.sessions import AsyncSessionsResource, SessionsResource


class TestSkyvernCloud:
    def test_init_with_api_key(self):
        client = SkyvernCloud(api_key="test-key")
        assert isinstance(client.sessions, SessionsResource)
        client.close()

    def test_init_from_env(self):
        with patch.dict(os.environ, {"SKYVERN_API_KEY": "env-key"}):
            client = SkyvernCloud()
            assert isinstance(client.sessions, SessionsResource)
            client.close()

    def test_init_raises_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="api_key must be provided"):
                SkyvernCloud()

    def test_contexts_returns_none(self):
        client = SkyvernCloud(api_key="test-key")
        assert client.contexts is None
        client.close()

    def test_capabilities(self):
        client = SkyvernCloud(api_key="test-key")
        assert "proxy" in client.capabilities
        client.close()

    def test_context_manager(self):
        with SkyvernCloud(api_key="test-key") as client:
            assert isinstance(client.sessions, SessionsResource)

    def test_custom_base_url(self):
        client = SkyvernCloud(api_key="key", base_url="https://custom.api.com")
        assert client._http._client.base_url == "https://custom.api.com"
        client.close()

    def test_custom_timeout(self):
        client = SkyvernCloud(api_key="key", timeout=30.0)
        client.close()


class TestAsyncSkyvernCloud:
    def test_init_with_api_key(self):
        client = AsyncSkyvernCloud(api_key="test-key")
        assert isinstance(client.sessions, AsyncSessionsResource)

    def test_init_raises_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="api_key must be provided"):
                AsyncSkyvernCloud()

    def test_contexts_returns_none(self):
        client = AsyncSkyvernCloud(api_key="test-key")
        assert client.contexts is None

    def test_capabilities(self):
        client = AsyncSkyvernCloud(api_key="test-key")
        assert client.capabilities == ["proxy"]

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with AsyncSkyvernCloud(api_key="test-key") as client:
            assert isinstance(client.sessions, AsyncSessionsResource)


class TestBackwardCompatibility:
    def test_skyvern_alias(self):
        from skyvern_lite import Skyvern
        assert Skyvern is SkyvernCloud

    def test_async_skyvern_alias(self):
        from skyvern_lite import AsyncSkyvern
        assert AsyncSkyvern is AsyncSkyvernCloud
