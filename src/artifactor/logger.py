"""Structured JSON logger for request and error tracking."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from artifactor.constants import ERROR_TRUNCATION_CHARS
from artifactor.logging_config import LOG_DATEFMT, LOG_FORMAT

__all__ = ["AgentLogger", "LOG_FORMAT", "LOG_DATEFMT"]


class AgentLogger:
    """Structured JSON logger with request_id correlation."""

    def __init__(self, log_dir: Path, level: str = "INFO") -> None:
        self._log_dir = log_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("artifactor.agent")
        self._logger.setLevel(getattr(logging, level.upper()))

        if not self._logger.handlers:
            handler = logging.FileHandler(log_dir / "agent.log")
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)

    def log_request(
        self,
        request_id: str,
        query: str,
        model: str,
        tokens: int,
        tools_called: list[str],
        duration_ms: float,
    ) -> None:
        self._logger.info(
            json.dumps({
                "type": "request",
                "timestamp": datetime.now(UTC).isoformat(),
                "request_id": request_id,
                "query": query[:ERROR_TRUNCATION_CHARS],
                "model": model,
                "tokens": tokens,
                "tools_called": tools_called,
                "duration_ms": duration_ms,
            })
        )

    def log_error(
        self,
        request_id: str,
        component: str,
        error: str,
    ) -> None:
        self._logger.error(
            json.dumps({
                "type": "error",
                "timestamp": datetime.now(UTC).isoformat(),
                "request_id": request_id,
                "component": component,
                "error": error,
            })
        )

    def log_stage(
        self,
        request_id: str,
        stage_name: str,
        status: str,
        duration_ms: float,
        error: str | None = None,
    ) -> None:
        self._logger.info(
            json.dumps({
                "type": "stage",
                "timestamp": datetime.now(UTC).isoformat(),
                "request_id": request_id,
                "stage": stage_name,
                "status": status,
                "duration_ms": duration_ms,
                "error": error,
            })
        )
