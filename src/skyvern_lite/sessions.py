"""Session CRUD resources for Skyvern cloud browser SDK."""

from __future__ import annotations

import time
from typing import Any

from .exceptions import SessionNotFoundError, TimeoutError
from .models import (
    COUNTRY_TO_PROXY_LOCATION,
    PROXY_SPECIAL,
    ContextAttach,
    FingerprintConfig,
    ManagedProxyConfig,
    ProxyConfig,
    RecordingConfig,
    SessionInfo,
    map_status,
)

_CDP_POLL_INITIAL = 0.5
_CDP_POLL_MAX = 3.0
_CDP_POLL_TIMEOUT = 30.0


def _to_session_info(
    data: dict[str, Any],
    delete_fn: Any = None,
) -> SessionInfo:
    """Map Skyvern API response dict to SessionInfo."""
    info = SessionInfo(
        session_id=data.get("browser_session_id", ""),
        cdp_url=data.get("browser_address"),
        status=map_status(data.get("status", "active")),
        created_at=data.get("created_at"),
        inspect_url=data.get("app_url"),
        metadata={
            k: v
            for k, v in data.items()
            if k not in {
                "browser_session_id",
                "browser_address",
                "status",
                "created_at",
                "app_url",
            }
        },
    )
    if delete_fn is not None:
        info.set_delete_fn(delete_fn)
    return info


def _build_create_body(
    browser_mode: str,
    proxy: ProxyConfig | ManagedProxyConfig | None,
    recording: RecordingConfig | None,
    fingerprint: FingerprintConfig | str | None,
    context: ContextAttach | None,
    vendor_params: dict[str, Any],
) -> dict[str, Any]:
    """Build the JSON body for POST v1/browser_sessions."""
    body: dict[str, Any] = {}

    # Proxy
    if isinstance(proxy, ProxyConfig):
        raise NotImplementedError(
            "Skyvern does not support custom proxy servers. "
            "Use ManagedProxyConfig(country='US') instead."
        )
    if isinstance(proxy, ManagedProxyConfig):
        key = proxy.country.upper()
        location = COUNTRY_TO_PROXY_LOCATION.get(key) or PROXY_SPECIAL.get(key)
        if location is None:
            raise ValueError(
                f"Unsupported proxy country: {proxy.country}. "
                f"Supported: {sorted(COUNTRY_TO_PROXY_LOCATION.keys())} "
                f"Special: {sorted(PROXY_SPECIAL.keys())}"
            )
        body["proxy_location"] = location

    # Pass-through vendor params
    # NOTE: timeout is in MINUTES (5–1440), not seconds.
    passthrough_keys = {
        "timeout",
        "extensions",
        "browser_type",
    }
    for key in passthrough_keys:
        if key in vendor_params:
            body[key] = vendor_params[key]

    return body


class SessionsResource:
    """Synchronous session CRUD operations."""

    def __init__(self, http: Any) -> None:
        self._http = http

    def create(
        self,
        *,
        browser_mode: str = "normal",
        proxy: ProxyConfig | ManagedProxyConfig | None = None,
        recording: RecordingConfig | None = None,
        fingerprint: FingerprintConfig | str | None = None,
        context: ContextAttach | None = None,
        **vendor_params: Any,
    ) -> SessionInfo:
        """Create a browser session.

        Returns a SessionInfo with cdp_url ready for connection.
        Polls for cdp_url if not immediately available (up to 30s).
        """
        body = _build_create_body(
            browser_mode, proxy, recording, fingerprint, context, vendor_params
        )
        data = self._http.request("POST", "/v1/browser_sessions", json=body)

        session_id = data.get("browser_session_id", "")

        # Poll for cdp_url if not immediately available
        if not data.get("browser_address"):
            data = self._poll_for_cdp_url(session_id)

        def _delete() -> None:
            self.delete(session_id)

        return _to_session_info(data, delete_fn=_delete)

    def get(self, session_id: str) -> SessionInfo:
        """Get session info by ID."""
        data = self._http.request("GET", f"/v1/browser_sessions/{session_id}")
        return _to_session_info(data)

    def list(self, **filters: Any) -> list[SessionInfo]:
        """List sessions, optionally filtered."""
        params = filters if filters else None
        data = self._http.request("GET", "/v1/browser_sessions", params=params)
        if isinstance(data, list):
            return [_to_session_info(item) for item in data]
        # Some APIs wrap in {"items": [...]} or {"browser_sessions": [...]}
        items = data.get("browser_sessions") or data.get("items") or []
        return [_to_session_info(item) for item in items]

    def delete(self, session_id: str) -> None:
        """Delete (close) a session. Idempotent — ignores 404/409."""
        try:
            self._http.request("POST", f"/v1/browser_sessions/{session_id}/close")
        except SessionNotFoundError:
            pass  # Already deleted

    def _poll_for_cdp_url(self, session_id: str) -> dict[str, Any]:
        """Poll GET until browser_address is available."""
        deadline = time.monotonic() + _CDP_POLL_TIMEOUT
        interval = _CDP_POLL_INITIAL

        while True:
            data = self._http.request("GET", f"/v1/browser_sessions/{session_id}")
            if data.get("browser_address"):
                return data

            if time.monotonic() + interval > deadline:
                raise TimeoutError(
                    f"cdp_url not available after {_CDP_POLL_TIMEOUT}s for session {session_id}"
                )

            time.sleep(interval)
            interval = min(interval * 2, _CDP_POLL_MAX)


class AsyncSessionsResource:
    """Asynchronous session CRUD operations."""

    def __init__(self, http: Any) -> None:
        self._http = http

    async def create(
        self,
        *,
        browser_mode: str = "normal",
        proxy: ProxyConfig | ManagedProxyConfig | None = None,
        recording: RecordingConfig | None = None,
        fingerprint: FingerprintConfig | str | None = None,
        context: ContextAttach | None = None,
        **vendor_params: Any,
    ) -> SessionInfo:
        """Create a browser session (async).

        Returns a SessionInfo with cdp_url ready for connection.
        Polls for cdp_url if not immediately available (up to 30s).
        """
        body = _build_create_body(
            browser_mode, proxy, recording, fingerprint, context, vendor_params
        )
        data = await self._http.request("POST", "/v1/browser_sessions", json=body)

        session_id = data.get("browser_session_id", "")

        if not data.get("browser_address"):
            data = await self._poll_for_cdp_url(session_id)

        def _delete() -> None:
            # For async context manager, we need a sync shim.
            # Users should prefer explicit await client.sessions.delete().
            import asyncio

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(self.delete(session_id))
            else:
                asyncio.run(self.delete(session_id))

        return _to_session_info(data, delete_fn=_delete)

    async def get(self, session_id: str) -> SessionInfo:
        """Get session info by ID (async)."""
        data = await self._http.request("GET", f"/v1/browser_sessions/{session_id}")
        return _to_session_info(data)

    async def list(self, **filters: Any) -> list[SessionInfo]:
        """List sessions (async), optionally filtered."""
        params = filters if filters else None
        data = await self._http.request("GET", "/v1/browser_sessions", params=params)
        if isinstance(data, list):
            return [_to_session_info(item) for item in data]
        items = data.get("browser_sessions") or data.get("items") or []
        return [_to_session_info(item) for item in items]

    async def delete(self, session_id: str) -> None:
        """Delete (close) a session (async). Idempotent — ignores 404/409."""
        try:
            await self._http.request(
                "POST", f"/v1/browser_sessions/{session_id}/close"
            )
        except SessionNotFoundError:
            pass

    async def _poll_for_cdp_url(self, session_id: str) -> dict[str, Any]:
        """Poll GET until browser_address is available (async)."""
        import asyncio

        deadline = time.monotonic() + _CDP_POLL_TIMEOUT
        interval = _CDP_POLL_INITIAL

        while True:
            data = await self._http.request(
                "GET", f"/v1/browser_sessions/{session_id}"
            )
            if data.get("browser_address"):
                return data

            if time.monotonic() + interval > deadline:
                raise TimeoutError(
                    f"cdp_url not available after {_CDP_POLL_TIMEOUT}s for session {session_id}"
                )

            await asyncio.sleep(interval)
            interval = min(interval * 2, _CDP_POLL_MAX)
