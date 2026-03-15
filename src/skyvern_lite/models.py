"""Data models for cloud browser SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Status mapping: Skyvern → spec
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[str, str] = {
    "created": "active",
    "running": "active",
    "completed": "closed",
    "failed": "error",
    "timeout": "error",
}


def map_status(skyvern_status: str) -> str:
    """Map a Skyvern status string to the unified spec status."""
    return _STATUS_MAP.get(skyvern_status, skyvern_status)


# ---------------------------------------------------------------------------
# Proxy location mapping: ISO country code → Skyvern ProxyLocation enum value
# ---------------------------------------------------------------------------

COUNTRY_TO_PROXY_LOCATION: dict[str, str] = {
    # From Skyvern OpenAPI spec (ProxyLocation enum)
    "US": "RESIDENTIAL",
    "AR": "RESIDENTIAL_AR",
    "AU": "RESIDENTIAL_AU",
    "BR": "RESIDENTIAL_BR",
    "CA": "RESIDENTIAL_CA",
    "DE": "RESIDENTIAL_DE",
    "ES": "RESIDENTIAL_ES",
    "FR": "RESIDENTIAL_FR",
    "GB": "RESIDENTIAL_GB",
    "IE": "RESIDENTIAL_IE",
    "IN": "RESIDENTIAL_IN",
    "IT": "RESIDENTIAL_IT",
    "JP": "RESIDENTIAL_JP",
    "KR": "RESIDENTIAL_KR",
    "MX": "RESIDENTIAL_MX",
    "NL": "RESIDENTIAL_NL",
    "NZ": "RESIDENTIAL_NZ",
    "PH": "RESIDENTIAL_PH",
    "TR": "RESIDENTIAL_TR",
    "ZA": "RESIDENTIAL_ZA",
}

# Special proxy values (not country-based)
PROXY_SPECIAL: dict[str, str] = {
    "ISP": "RESIDENTIAL_ISP",
    "NONE": "NONE",
}


# ---------------------------------------------------------------------------
# Configuration models
# ---------------------------------------------------------------------------


class ManagedProxyConfig(BaseModel):
    """Managed proxy configuration — provider handles the proxy.

    Maps country code to Skyvern's proxy_location enum.
    """

    country: str
    city: str | None = None


class ProxyConfig(BaseModel):
    """Custom proxy configuration (server + credentials).

    Note: Skyvern does not support custom proxies. Using this will raise
    NotImplementedError at session creation time.
    """

    server: str
    username: str | None = None
    password: str | None = None


class RecordingConfig(BaseModel):
    """Recording configuration."""

    enabled: bool = True


class ViewportConfig(BaseModel):
    """Viewport dimensions."""

    width: int = 1920
    height: int = 1080
    device_scale_factor: float = 1.0
    is_mobile: bool = False


class FingerprintConfig(BaseModel):
    """Browser fingerprint configuration. All fields optional."""

    user_agent: str | None = None
    viewport: ViewportConfig | None = None
    locale: str | None = None
    timezone: str | None = None
    webgl_vendor: str | None = None
    webgl_renderer: str | None = None
    platform: str | None = None


class ContextAttach(BaseModel):
    """Context attachment for session creation."""

    context_id: str
    mode: str = "read_write"


# ---------------------------------------------------------------------------
# SessionInfo
# ---------------------------------------------------------------------------


class SessionInfo(BaseModel):
    """Browser session information returned by create/get/list."""

    session_id: str
    cdp_url: str | None = None
    status: str = "active"
    created_at: datetime | None = None
    inspect_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Internal: deletion callback for context manager support.
    # Excluded from serialization.
    _delete_fn: Callable[[], None] | None = None

    model_config = {"arbitrary_types_allowed": True}

    def set_delete_fn(self, fn: Callable[[], None]) -> None:
        """Attach a deletion callback for context manager support."""
        object.__setattr__(self, "_delete_fn", fn)

    # --- Context manager protocol ---

    def __enter__(self) -> "SessionInfo":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        fn = getattr(self, "_delete_fn", None)
        if fn is not None:
            fn()
