"""Tests for error classification."""

from __future__ import annotations

from artifactor.resilience.errors import (
    ErrorClass,
    classify_error,
    is_retryable,
)


class _StatusCodeError(Exception):
    """Exception with a status_code attribute."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


# ── classify_error ───────────────────────────────────────────


def test_classify_status_code_429_as_transient() -> None:
    """Exception with status_code=429 → TRANSIENT."""
    err = _StatusCodeError("rate limited", 429)
    assert classify_error(err) == ErrorClass.TRANSIENT


def test_classify_status_code_401_as_client() -> None:
    """Exception with status_code=401 → CLIENT."""
    err = _StatusCodeError("unauthorized", 401)
    assert classify_error(err) == ErrorClass.CLIENT


def test_classify_status_code_403_as_client() -> None:
    """Exception with status_code=403 → CLIENT."""
    err = _StatusCodeError("forbidden", 403)
    assert classify_error(err) == ErrorClass.CLIENT


def test_classify_status_code_500_as_server() -> None:
    """Exception with status_code=500 → SERVER."""
    err = _StatusCodeError("internal server error", 500)
    assert classify_error(err) == ErrorClass.SERVER


def test_classify_timeout_error_type() -> None:
    """TimeoutError instance → TIMEOUT (no string matching)."""
    assert classify_error(TimeoutError()) == ErrorClass.TIMEOUT


def test_classify_asyncio_timeout_error() -> None:
    """asyncio.TimeoutError → TIMEOUT."""
    assert (
        classify_error(TimeoutError())
        == ErrorClass.TIMEOUT
    )


def test_classify_string_fallback_rate_limit() -> None:
    """'rate limit' in message → TRANSIENT (string fallback)."""
    err = Exception("rate limit exceeded for model xyz")
    assert classify_error(err) == ErrorClass.TRANSIENT


def test_classify_string_fallback_connection() -> None:
    """'connection' in message → TRANSIENT."""
    err = Exception("connection refused to host")
    assert classify_error(err) == ErrorClass.TRANSIENT


def test_classify_string_fallback_timeout() -> None:
    """'timed out' in message → TIMEOUT."""
    err = Exception("request timed out after 30s")
    assert classify_error(err) == ErrorClass.TIMEOUT


def test_classify_unknown() -> None:
    """Unrecognized exception → UNKNOWN."""
    err = Exception("something completely unexpected")
    assert classify_error(err) == ErrorClass.UNKNOWN


# ── is_retryable ─────────────────────────────────────────────


def test_is_retryable_true_for_transient() -> None:
    """TRANSIENT, SERVER, TIMEOUT are retryable."""
    assert is_retryable(_StatusCodeError("", 429)) is True
    assert is_retryable(_StatusCodeError("", 500)) is True
    assert is_retryable(TimeoutError()) is True


def test_is_retryable_false_for_client() -> None:
    """CLIENT and UNKNOWN are not retryable."""
    assert is_retryable(_StatusCodeError("", 401)) is False
    assert is_retryable(Exception("mystery")) is False
