"""Tests for _cas_set_status helper."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from artifactor.api.routes.projects import _cas_set_status
from artifactor.constants import ProjectStatus


@pytest.mark.asyncio
async def test_cas_set_status_success() -> None:
    """CAS delegates to ProjectService.try_set_status_immediate."""
    service = AsyncMock()
    service.try_set_status_immediate.return_value = True

    await _cas_set_status(
        service, "proj-1", ProjectStatus.ANALYZED
    )

    service.try_set_status_immediate.assert_awaited_once_with(
        "proj-1",
        {ProjectStatus.ANALYZING},
        ProjectStatus.ANALYZED,
    )


@pytest.mark.asyncio
async def test_cas_set_status_noop_when_paused() -> None:
    """CAS is no-op when status is PAUSED (service returns False)."""
    service = AsyncMock()
    service.try_set_status_immediate.return_value = False

    # Should not raise
    await _cas_set_status(
        service, "proj-1", ProjectStatus.ERROR
    )

    service.try_set_status_immediate.assert_awaited_once()


@pytest.mark.asyncio
async def test_cas_set_status_logs_on_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Service exception is caught and logged, not raised."""
    service = AsyncMock()
    service.try_set_status_immediate.side_effect = RuntimeError(
        "db down"
    )

    with caplog.at_level(logging.ERROR):
        await _cas_set_status(
            service, "proj-1", ProjectStatus.ERROR
        )

    assert "done_callback_failed" in caplog.text
    assert "proj-1" in caplog.text
