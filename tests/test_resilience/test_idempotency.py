"""Tests for IdempotencyGuard."""

from __future__ import annotations

import asyncio

import pytest

from artifactor.resilience.idempotency import IdempotencyGuard


@pytest.mark.asyncio
async def test_deduplicates_concurrent_calls() -> None:
    """Two concurrent calls with same key → only one executes."""
    guard = IdempotencyGuard()
    call_count = 0

    async def _slow_op() -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return "result"

    r1, r2 = await asyncio.gather(
        guard.execute("key1", _slow_op),
        guard.execute("key1", _slow_op),
    )
    assert r1 == "result"
    assert r2 == "result"
    assert call_count == 1  # only one execution


@pytest.mark.asyncio
async def test_independent_keys_run_separately() -> None:
    """Different keys → both execute independently."""
    guard = IdempotencyGuard()
    call_count = 0

    async def _op() -> str:
        nonlocal call_count
        call_count += 1
        return "ok"

    r1, r2 = await asyncio.gather(
        guard.execute("key_a", _op),
        guard.execute("key_b", _op),
    )
    assert r1 == "ok"
    assert r2 == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_error_propagates_to_waiters() -> None:
    """First call raises → second caller gets same error."""
    guard = IdempotencyGuard()

    async def _failing_op() -> str:
        await asyncio.sleep(0.05)
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await asyncio.gather(
            guard.execute("key1", _failing_op),
            guard.execute("key1", _failing_op),
        )


@pytest.mark.asyncio
async def test_active_keys_observable() -> None:
    """During execution, active_keys contains the key."""
    guard = IdempotencyGuard()
    seen_keys: list[list[str]] = []

    async def _op() -> str:
        seen_keys.append(guard.active_keys)
        await asyncio.sleep(0.01)
        return "done"

    await guard.execute("test_key", _op)
    assert ["test_key"] in seen_keys


@pytest.mark.asyncio
async def test_cleanup_after_completion() -> None:
    """After execution, key removed from _in_flight."""
    guard = IdempotencyGuard()

    async def _op() -> str:
        return "done"

    await guard.execute("key1", _op)
    assert guard.active_keys == []


@pytest.mark.asyncio
async def test_cancelled_error_propagates_to_waiters() -> None:
    """CancelledError (BaseException) propagates to waiters."""
    guard = IdempotencyGuard()

    async def _cancelling_op() -> str:
        await asyncio.sleep(0.05)
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.gather(
            guard.execute("key1", _cancelling_op),
            guard.execute("key1", _cancelling_op),
        )

    # Key should be cleaned up
    assert guard.active_keys == []


@pytest.mark.asyncio
async def test_three_concurrent_callers_no_duplicate() -> None:
    """Three concurrent calls with same key → only one executes."""
    guard = IdempotencyGuard()
    call_count = 0

    async def _slow_op() -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return "triple"

    r1, r2, r3 = await asyncio.gather(
        guard.execute("key1", _slow_op),
        guard.execute("key1", _slow_op),
        guard.execute("key1", _slow_op),
    )
    assert r1 == "triple"
    assert r2 == "triple"
    assert r3 == "triple"
    assert call_count == 1
