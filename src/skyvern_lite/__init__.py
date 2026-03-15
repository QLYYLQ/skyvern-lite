"""Skyvern Cloud Browser SDK — minimal interface for browser session lifecycle.

Quick Start
-----------
::

    from skyvern_lite import SkyvernCloud

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
- ``timeout: int``              — Session timeout in **minutes** (5–1440, default: 60)
- ``extensions: list[str]``     — Browser extensions. Valid values:
                                  ``"ad-blocker"`` | ``"captcha-solver"``
                                  Can combine: ``extensions=["ad-blocker", "captcha-solver"]``
- ``browser_type: str``         — ``"chrome"`` or ``"msedge"``

Example with all features::

    session = client.sessions.create(
        proxy=ManagedProxyConfig(country="US"),
        extensions=["ad-blocker", "captcha-solver"],
        browser_type="chrome",
        timeout=120,  # 120 minutes
    )

Feature Support Matrix
~~~~~~~~~~~~~~~~~~~~~~
=========================  =========  ==================================================
Feature                    Supported  Notes
=========================  =========  ==================================================
Residential proxy          Yes        20 countries (from Skyvern OpenAPI spec)
Ad blocker extension       Yes        ``extensions=["ad-blocker"]``
Captcha solver extension   Yes        ``extensions=["captcha-solver"]``
Browser type selection     Yes        ``"chrome"`` or ``"msedge"``
Custom session timeout     Yes        ``timeout=120`` (minutes, range 5–1440)
Browser fingerprint        No         Skyvern API does not accept fingerprint parameters
Custom proxy server        No         Only managed proxies; ``ProxyConfig`` raises error
Browser profile            No         Requires Skyvern Task/Workflow, not usable via CDP
=========================  =========  ==================================================

SessionInfo Fields
~~~~~~~~~~~~~~~~~~
- ``session_id: str``           — Unique session identifier
- ``cdp_url: str | None``       — CDP WebSocket URL (ws:// or wss://)
- ``status: str``               — "active", "closed", or "error"
- ``created_at: datetime | None``
- ``inspect_url: str | None``   — Human-readable debug URL (Skyvern dashboard)
- ``metadata: dict``            — Vendor-specific data (proxy_location, timeout, etc.)
- ``metadata["recordings"]``    — Auto-generated session recording URLs (.webm)

Proxy Configuration
~~~~~~~~~~~~~~~~~~~
- ``ManagedProxyConfig(country="US")``       — Use Skyvern's managed residential proxy
- ``ManagedProxyConfig(country="ISP")``      — ISP proxy (non-residential)
- ``ManagedProxyConfig(country="NONE")``     — Explicitly disable proxy
- ``ProxyConfig(server, username, password)`` — NOT supported (raises NotImplementedError)

Supported proxy countries (from Skyvern OpenAPI spec, verified with IP geolocation):
US, AR, AU, BR, CA, DE, ES, FR, GB, IE, IN, IT, JP, KR, MX, NL, NZ, PH, TR, ZA.

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
