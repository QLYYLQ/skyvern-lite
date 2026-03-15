"""Internal HTTP client wrappers with retry and exception mapping."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .exceptions import (
    AuthenticationError,
    CloudBrowserError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
    TimeoutError,
)

_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_DEFAULT_BACKOFF_BASE = 0.5
_DEFAULT_BACKOFF_MAX = 3.0


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse Retry-After header value in seconds."""
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _raise_for_status(response: httpx.Response) -> None:
    """Map HTTP status codes to SDK exceptions."""
    status = response.status_code
    if 200 <= status < 300:
        return

    try:
        body = response.json()
    except Exception:
        body = {}

    message = body.get("detail") or body.get("message") or response.text or f"HTTP {status}"
    request_id = response.headers.get("x-request-id")

    if status in (401, 403):
        raise AuthenticationError(str(message))
    if status == 404:
        raise SessionNotFoundError(str(message))
    if status == 429:
        retry_after_val = _parse_retry_after(response)
        retry_after_int = int(retry_after_val) if retry_after_val is not None else None
        raise QuotaExceededError(str(message), retry_after=retry_after_int)
    if status >= 500:
        raise ProviderError(
            str(message),
            status_code=status,
            request_id=request_id,
        )
    raise CloudBrowserError(f"HTTP {status}: {message}")


class SyncHttpClient:
    """Synchronous HTTP client with retry logic."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        self._client = httpx.Client(
            base_url=base_url,
            headers={"x-api-key": api_key},
            timeout=timeout,
        )
        self._max_retries = max_retries

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an HTTP request with retry on transient errors."""
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(
                    method, path, json=json, params=params
                )
            except httpx.TimeoutException as exc:
                last_exc = TimeoutError(str(exc))
                if attempt < self._max_retries:
                    self._backoff(attempt)
                    continue
                raise last_exc from exc
            except httpx.ConnectError as exc:
                last_exc = NetworkError(str(exc))
                if attempt < self._max_retries:
                    self._backoff(attempt)
                    continue
                raise last_exc from exc

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                wait = _parse_retry_after(response) or self._backoff_delay(attempt)
                time.sleep(wait)
                continue

            _raise_for_status(response)

            if response.status_code == 204 or not response.content:
                return {}
            return response.json()  # type: ignore[no-any-return]

        # Should not reach here, but just in case
        if last_exc is not None:
            raise last_exc
        raise CloudBrowserError("Request failed after retries")

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        return min(_DEFAULT_BACKOFF_BASE * (2**attempt), _DEFAULT_BACKOFF_MAX)

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(min(_DEFAULT_BACKOFF_BASE * (2**attempt), _DEFAULT_BACKOFF_MAX))


class AsyncHttpClient:
    """Asynchronous HTTP client with retry logic."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"x-api-key": api_key},
            timeout=timeout,
        )
        self._max_retries = max_retries

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an async HTTP request with retry on transient errors."""
        import asyncio

        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(
                    method, path, json=json, params=params
                )
            except httpx.TimeoutException as exc:
                last_exc = TimeoutError(str(exc))
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue
                raise last_exc from exc
            except httpx.ConnectError as exc:
                last_exc = NetworkError(str(exc))
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue
                raise last_exc from exc

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                wait = _parse_retry_after(response) or self._backoff_delay(attempt)
                await asyncio.sleep(wait)
                continue

            _raise_for_status(response)

            if response.status_code == 204 or not response.content:
                return {}
            return response.json()  # type: ignore[no-any-return]

        if last_exc is not None:
            raise last_exc
        raise CloudBrowserError("Request failed after retries")

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        return min(_DEFAULT_BACKOFF_BASE * (2**attempt), _DEFAULT_BACKOFF_MAX)
