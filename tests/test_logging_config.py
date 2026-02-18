"""Tests for two-phase singleton logging configuration."""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

import pytest

from artifactor.logging_config import (
    _SUPPRESSED_LOGGERS,
    LOG_DATEFMT,
    LOG_FORMAT,
    cleanup_third_party_handlers,
    setup_logging,
)


@pytest.fixture(autouse=True)
def _reset_flags() -> None:
    """Reset singleton flags before each test."""
    import artifactor.logging_config as mod

    mod._phase1_done = False
    mod._phase2_done = False


def test_setup_logging_is_idempotent() -> None:
    """Phase 1 executes once even when called twice."""
    with patch("artifactor.logging_config.logging.basicConfig") as mock_bc:
        setup_logging()
        setup_logging()  # second call is no-op
        mock_bc.assert_called_once()


def test_litellm_log_env_var_set() -> None:
    """Phase 1 sets LITELLM_LOG=WARNING before litellm import."""
    # Remove env var if present
    os.environ.pop("LITELLM_LOG", None)
    setup_logging()
    assert os.environ.get("LITELLM_LOG") == "WARNING"


def test_litellm_log_env_var_preserves_existing() -> None:
    """Phase 1 uses setdefault — doesn't overwrite user-set value."""
    os.environ["LITELLM_LOG"] = "ERROR"
    try:
        setup_logging()
        assert os.environ["LITELLM_LOG"] == "ERROR"
    finally:
        os.environ.pop("LITELLM_LOG", None)


def test_suppressed_loggers_at_warning() -> None:
    """Phase 1 sets all suppressed loggers to WARNING level."""
    setup_logging()
    for name in _SUPPRESSED_LOGGERS:
        lg = logging.getLogger(name)
        assert lg.level == logging.WARNING, (
            f"Logger {name!r} level is {lg.level}, expected WARNING"
        )


def test_cleanup_clears_litellm_handlers() -> None:
    """Phase 2 removes litellm's duplicate StreamHandlers."""
    # Simulate litellm adding its own handler
    lg = logging.getLogger("LiteLLM")
    handler = logging.StreamHandler()
    lg.addHandler(handler)
    assert len(lg.handlers) >= 1

    cleanup_third_party_handlers()
    assert len(lg.handlers) == 0


def test_cleanup_enables_propagation() -> None:
    """Phase 2 enables propagation so messages reach root."""
    lg = logging.getLogger("LiteLLM")
    lg.propagate = False

    cleanup_third_party_handlers()
    assert lg.propagate is True


def test_cleanup_is_idempotent() -> None:
    """Phase 2 executes once even when called twice."""
    # Add a handler
    lg = logging.getLogger("LiteLLM")
    lg.addHandler(logging.StreamHandler())

    cleanup_third_party_handlers()
    assert len(lg.handlers) == 0

    # Add another handler — second call should NOT clear it
    # (because the flag prevents re-execution)
    lg.addHandler(logging.StreamHandler())
    cleanup_third_party_handlers()
    assert len(lg.handlers) == 1  # still there — phase2 was no-op


def test_log_format_constants() -> None:
    """LOG_FORMAT and LOG_DATEFMT are non-empty strings."""
    assert isinstance(LOG_FORMAT, str)
    assert len(LOG_FORMAT) > 0
    assert isinstance(LOG_DATEFMT, str)
    assert len(LOG_DATEFMT) > 0
