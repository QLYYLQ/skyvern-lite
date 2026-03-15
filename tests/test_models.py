"""Tests for data models."""

import pytest

from skyvern_lite.models import (
    COUNTRY_TO_PROXY_LOCATION,
    ContextAttach,
    FingerprintConfig,
    ManagedProxyConfig,
    ProxyConfig,
    RecordingConfig,
    SessionInfo,
    ViewportConfig,
    map_status,
)


class TestStatusMapping:
    def test_created_maps_to_active(self):
        assert map_status("created") == "active"

    def test_running_maps_to_active(self):
        assert map_status("running") == "active"

    def test_completed_maps_to_closed(self):
        assert map_status("completed") == "closed"

    def test_failed_maps_to_error(self):
        assert map_status("failed") == "error"

    def test_timeout_maps_to_error(self):
        assert map_status("timeout") == "error"

    def test_unknown_passthrough(self):
        assert map_status("unknown_status") == "unknown_status"


class TestSessionInfo:
    def test_required_fields(self):
        info = SessionInfo(
            session_id="s1",
            cdp_url="wss://example.com/devtools",
            status="active",
        )
        assert info.session_id == "s1"
        assert info.cdp_url == "wss://example.com/devtools"
        assert info.status == "active"

    def test_optional_fields_default(self):
        info = SessionInfo(session_id="s1")
        assert info.cdp_url is None
        assert info.created_at is None
        assert info.inspect_url is None
        assert info.metadata == {}

    def test_context_manager_calls_delete(self):
        called = False

        def _delete():
            nonlocal called
            called = True

        info = SessionInfo(session_id="s1", cdp_url="ws://test")
        info.set_delete_fn(_delete)

        with info as s:
            assert s.session_id == "s1"

        assert called

    def test_context_manager_without_delete_fn(self):
        info = SessionInfo(session_id="s1")
        with info:
            pass  # should not raise

    def test_context_manager_calls_delete_on_exception(self):
        called = False

        def _delete():
            nonlocal called
            called = True

        info = SessionInfo(session_id="s1", cdp_url="ws://test")
        info.set_delete_fn(_delete)

        with pytest.raises(ValueError, match="test error"):
            with info:
                raise ValueError("test error")

        assert called

    def test_metadata_dict(self):
        info = SessionInfo(
            session_id="s1",
            metadata={"region": "us-east-1", "container_id": "abc"},
        )
        assert info.metadata["region"] == "us-east-1"


class TestProxyModels:
    def test_managed_proxy_config(self):
        cfg = ManagedProxyConfig(country="US")
        assert cfg.country == "US"
        assert cfg.city is None

    def test_managed_proxy_config_with_city(self):
        cfg = ManagedProxyConfig(country="US", city="New York")
        assert cfg.city == "New York"

    def test_proxy_config(self):
        cfg = ProxyConfig(server="http://proxy:8080", username="u", password="p")
        assert cfg.server == "http://proxy:8080"

    def test_country_mapping_us(self):
        assert COUNTRY_TO_PROXY_LOCATION["US"] == "RESIDENTIAL"

    def test_country_mapping_gb(self):
        assert COUNTRY_TO_PROXY_LOCATION["GB"] == "RESIDENTIAL_GB"

    def test_country_mapping_has_entries(self):
        assert len(COUNTRY_TO_PROXY_LOCATION) >= 20


class TestConfigModels:
    def test_recording_config(self):
        cfg = RecordingConfig()
        assert cfg.enabled is True

    def test_viewport_config_defaults(self):
        cfg = ViewportConfig()
        assert cfg.width == 1920
        assert cfg.height == 1080
        assert cfg.device_scale_factor == 1.0
        assert cfg.is_mobile is False

    def test_fingerprint_config_all_none(self):
        cfg = FingerprintConfig()
        assert cfg.user_agent is None
        assert cfg.viewport is None

    def test_context_attach(self):
        ctx = ContextAttach(context_id="ctx-1", mode="read_only")
        assert ctx.context_id == "ctx-1"
        assert ctx.mode == "read_only"

    def test_context_attach_default_mode(self):
        ctx = ContextAttach(context_id="ctx-1")
        assert ctx.mode == "read_write"
