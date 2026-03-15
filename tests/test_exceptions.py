"""Tests for the exception hierarchy."""

from skyvern_lite.exceptions import (
    AuthenticationError,
    CloudBrowserError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
    TimeoutError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_cloud_browser_error(self):
        for exc_cls in [
            AuthenticationError,
            QuotaExceededError,
            SessionNotFoundError,
            ProviderError,
            TimeoutError,
            NetworkError,
        ]:
            assert issubclass(exc_cls, CloudBrowserError)

    def test_cloud_browser_error_is_exception(self):
        assert issubclass(CloudBrowserError, Exception)

    def test_catch_all_with_base_class(self):
        with __import__("pytest").raises(CloudBrowserError):
            raise AuthenticationError("bad key")

    def test_quota_exceeded_retry_after(self):
        exc = QuotaExceededError("rate limited", retry_after=30)
        assert exc.retry_after == 30
        assert str(exc) == "rate limited"

    def test_quota_exceeded_no_retry_after(self):
        exc = QuotaExceededError("rate limited")
        assert exc.retry_after is None

    def test_provider_error_attributes(self):
        exc = ProviderError("internal error", status_code=502, request_id="req-abc")
        assert exc.status_code == 502
        assert exc.request_id == "req-abc"
        assert str(exc) == "internal error"

    def test_provider_error_defaults(self):
        exc = ProviderError("fail")
        assert exc.status_code is None
        assert exc.request_id is None

    def test_simple_exceptions_message(self):
        for exc_cls in [
            AuthenticationError,
            SessionNotFoundError,
            TimeoutError,
            NetworkError,
        ]:
            exc = exc_cls("test message")
            assert str(exc) == "test message"
