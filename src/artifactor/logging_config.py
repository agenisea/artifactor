"""Singleton logging configuration — two-phase initialization.

Phase 1: setup_logging() — call BEFORE litellm is imported.
  Sets LITELLM_LOG env var and configures root logger.

Phase 2: cleanup_third_party_handlers() — call AFTER all imports.
  Clears litellm's duplicate StreamHandlers added at import time.

Both phases are idempotent (guarded by module-level flags).
"""

import logging
import os

LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S"

# Third-party loggers to suppress to WARNING
_SUPPRESSED_LOGGERS = (
    "LiteLLM",
    "LiteLLM Router",
    "LiteLLM Proxy",
    "openai._base_client",
    "httpx",
)

_phase1_done = False
_phase2_done = False


def setup_logging(level: str = "INFO") -> None:
    """Phase 1: Configure root logger and set env vars.

    Must be called BEFORE any artifactor imports that transitively
    pull in litellm. Idempotent — second call is a no-op.
    """
    global _phase1_done  # noqa: PLW0603
    if _phase1_done:
        return
    _phase1_done = True

    # 1. Set LITELLM_LOG env var BEFORE litellm is imported.
    #    litellm._logging reads this at import time to set handler level.
    os.environ.setdefault("LITELLM_LOG", "WARNING")

    # 2. Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=LOG_FORMAT,
        datefmt=LOG_DATEFMT,
    )

    # 3. Suppress noisy third-party loggers
    for name in _SUPPRESSED_LOGGERS:
        lg = logging.getLogger(name)
        lg.setLevel(logging.WARNING)


def cleanup_third_party_handlers() -> None:
    """Phase 2: Remove litellm's duplicate StreamHandlers.

    Must be called AFTER all imports are complete (i.e., after litellm
    has added its handlers). Typically called after all module-level
    imports in main.py.

    litellm._logging adds its own handler to each logger, causing
    messages to appear twice (litellm handler + root propagation).
    This clears them and lets messages propagate to root only.

    Idempotent — second call is a no-op.
    """
    global _phase2_done  # noqa: PLW0603
    if _phase2_done:
        return
    _phase2_done = True

    for name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
