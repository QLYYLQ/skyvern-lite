"""Skyvern Cloud Browser SDK — minimal interface for browser session lifecycle.

Quick Start
-----------
::

    from skyvern_client import SkyvernCloud

    client = SkyvernCloud(api_key="sk-...")  # or set SKYVERN_API_KEY env var

    # Create a cloud browser session
    session = client.sessions.create()
    print(session.cdp_url)   # wss://sessions.skyvern.com/...
    print(session.session_id)

    # Use with Playwright (or any CDP client)
    # NOTE: Skyvern's CDP WebSocket requires the x-api-key header.
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(
            session.cdp_url,
            headers={"x-api-key": "sk-..."},
        )
        page = browser.contexts[0].new_page()
        page.goto("https://example.com")

    # Cleanup
    client.sessions.delete(session.session_id)

    # Or use context manager for auto-cleanup:
    with client.sessions.create() as session:
        ...  # session auto-deleted on exit

API Reference
-------------

Client Classes
~~~~~~~~~~~~~~
- ``SkyvernCloud(api_key, *, base_url, timeout, max_retries)``  — Sync client
- ``AsyncSkyvernCloud(api_key, *, base_url, timeout, max_retries)`` — Async client
- ``Skyvern`` / ``AsyncSkyvern`` — Backward-compatible aliases

Client Properties
~~~~~~~~~~~~~~~~~
- ``client.sessions``     — SessionsResource for CRUD operations
- ``client.contexts``     — Always None (Skyvern has no context persistence API)
- ``client.capabilities`` — Returns ``["proxy"]``

Session CRUD (``client.sessions``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- ``create(*, browser_mode, proxy, recording, fingerprint, context, **vendor_params) -> SessionInfo``
- ``get(session_id) -> SessionInfo``
- ``list(**filters) -> list[SessionInfo]``
- ``delete(session_id) -> None``  (idempotent, safe to call multiple times)

Vendor Parameters (pass via ``**vendor_params`` in ``create()``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- ``timeout: int``              — Session timeout in seconds (default: 60)
- ``extensions: list[str]``     — Browser extensions. Valid values:
                                  ``"ad-blocker"`` | ``"captcha-solver"``
                                  Can combine: ``extensions=["ad-blocker", "captcha-solver"]``
- ``browser_type: str``         — ``"chrome"`` (Chrome 145) or ``"msedge"`` (Edge 143)
- ``browser_profile_id: str``   — Persistent browser profile ID (must be created from
                                  an existing session via Skyvern dashboard)

Example with all features::

    session = client.sessions.create(
        proxy=ManagedProxyConfig(country="US"),
        extensions=["ad-blocker", "captcha-solver"],
        browser_type="chrome",
        timeout=120,
    )

Feature Support Matrix
~~~~~~~~~~~~~~~~~~~~~~
=========================  =========  ==================================================
Feature                    Supported  Notes
=========================  =========  ==================================================
Residential proxy          Yes        30+ countries, real residential IPs
Ad blocker extension       Yes        ``extensions=["ad-blocker"]``
Captcha solver extension   Yes        ``extensions=["captcha-solver"]``
Browser type selection     Yes        ``"chrome"`` or ``"msedge"``
Custom session timeout     Yes        ``timeout=300`` (seconds)
Browser fingerprint        No         Skyvern API does not accept fingerprint parameters
Custom proxy server        No         Only managed proxies; ``ProxyConfig`` raises error
Browser profile            Partial    Must pre-create from existing session
=========================  =========  ==================================================

SessionInfo Fields
~~~~~~~~~~~~~~~~~~
- ``session_id: str``           — Unique session identifier
- ``cdp_url: str | None``       — CDP WebSocket URL (ws:// or wss://)
- ``status: str``               — "active", "closed", or "error"
- ``created_at: datetime | None``
- ``inspect_url: str | None``   — Human-readable debug URL (Skyvern dashboard)
- ``metadata: dict``            — Vendor-specific data (proxy_location, timeout, etc.)

Proxy Configuration
~~~~~~~~~~~~~~~~~~~
- ``ManagedProxyConfig(country="US")``       — Use Skyvern's managed residential proxy
- ``ProxyConfig(server, username, password)`` — NOT supported (raises NotImplementedError)

Supported proxy countries (verified with real IP geolocation):
US, GB, DE, FR, JP, CA, AU, BR, IN, KR, AT, BE, BG, CH, CZ, ES, FI, GR,
IE, IL, IT, MX, NL, NO, PL, RO, RU, SE, SK, TR, ZA.

CDP Authentication
~~~~~~~~~~~~~~~~~~
Skyvern's CDP WebSocket endpoint requires authentication via the ``x-api-key``
header. When connecting with Playwright::

    browser = pw.chromium.connect_over_cdp(
        session.cdp_url,
        headers={"x-api-key": api_key},
    )

CDP capabilities available after connection:
- ``DOM.getDocument`` / ``DOM.querySelector`` / ``DOM.getOuterHTML`` — DOM tree
- ``Accessibility.getFullAXTree`` — Accessibility tree
- ``Page.captureScreenshot`` — Screenshots
- ``Input.dispatchMouseEvent`` / ``Input.dispatchKeyEvent`` — Input simulation
- All standard Chrome DevTools Protocol commands

Exception Hierarchy
~~~~~~~~~~~~~~~~~~~
::

    CloudBrowserError          # Base exception
    ├── AuthenticationError    # 401/403 — invalid or expired API key
    ├── QuotaExceededError     # 429 — rate limit (has .retry_after attribute)
    ├── SessionNotFoundError   # 404 — session doesn't exist
    ├── ProviderError          # 5xx — server error (has .status_code, .request_id)
    ├── TimeoutError           # Operation timed out
    └── NetworkError           # Connection failure
"""

from .client import AsyncSkyvernCloud, SkyvernCloud
from .exceptions import (
    AuthenticationError,
    CloudBrowserError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
    TimeoutError,
)
from .models import (
    ContextAttach,
    FingerprintConfig,
    ManagedProxyConfig,
    ProxyConfig,
    RecordingConfig,
    SessionInfo,
    ViewportConfig,
)

# Backward compatibility aliases
Skyvern = SkyvernCloud
AsyncSkyvern = AsyncSkyvernCloud

__all__ = [
    # Clients
    "SkyvernCloud",
    "AsyncSkyvernCloud",
    "Skyvern",
    "AsyncSkyvern",
    # Models
    "SessionInfo",
    "ContextAttach",
    "FingerprintConfig",
    "ViewportConfig",
    "ProxyConfig",
    "ManagedProxyConfig",
    "RecordingConfig",
    # Exceptions
    "CloudBrowserError",
    "AuthenticationError",
    "QuotaExceededError",
    "SessionNotFoundError",
    "ProviderError",
    "TimeoutError",
    "NetworkError",
]
