"""Error classification for structured error handling.

Classifies exceptions by category to enable:
- Structured logging (which errors are transient vs permanent)
- Informative user messages (timeout vs auth vs server)
- Future retry logic (only retry transient/server/timeout)
"""

from __future__ import annotations

import asyncio
from enum import Enum


class ErrorClass(Enum):
    TRANSIENT = "transient"  # 429, network errors — retryable
    SERVER = "server"  # 500, 502, 503 — retryable
    TIMEOUT = "timeout"  # deadline exceeded — retryable with backoff
    CLIENT = "client"  # 400, 401, 403 — do NOT retry
    UNKNOWN = "unknown"  # unclassified — do NOT retry


def classify_error(error: Exception) -> ErrorClass:
    """Classify an error to determine handling strategy.

    Checks structured attributes first (status_code), falls back
    to string matching for untyped exceptions.
    """
    # 1. Check for structured status_code attribute (httpx, openai, litellm)
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        if status_code == 429:
            return ErrorClass.TRANSIENT
        if 400 <= status_code < 500:
            return ErrorClass.CLIENT
        if 500 <= status_code < 600:
            return ErrorClass.SERVER

    # 2. Check for timeout types
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return ErrorClass.TIMEOUT

    # 3. Fall back to string matching for untyped exceptions
    msg = str(error).lower()

    if "timeout" in msg or "timed out" in msg:
        return ErrorClass.TIMEOUT
    if "429" in msg or "rate limit" in msg or "rate_limit" in msg:
        return ErrorClass.TRANSIENT
    if any(code in msg for code in ("500", "502", "503", "504")):
        return ErrorClass.SERVER
    if "econnrefused" in msg or "connection" in msg:
        return ErrorClass.TRANSIENT
    if any(code in msg for code in ("400", "401", "403", "404")):
        return ErrorClass.CLIENT

    return ErrorClass.UNKNOWN


_RETRYABLE = frozenset({
    ErrorClass.TRANSIENT,
    ErrorClass.SERVER,
    ErrorClass.TIMEOUT,
})


def is_retryable(error: Exception) -> bool:
    """Return True if the error category supports retry."""
    return classify_error(error) in _RETRYABLE
