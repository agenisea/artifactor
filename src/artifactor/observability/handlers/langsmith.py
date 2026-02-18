# pyright: reportUnusedFunction=false
"""LangSmith trace handler -- maps events to LangSmith runs.

Lazy-imports langsmith. Never a hard dependency.
"""

from __future__ import annotations

import logging
from typing import Any

from artifactor.observability.events import TraceEvent

logger = logging.getLogger(__name__)


class LangSmithTraceHandler:
    """Maps trace events to LangSmith run hierarchy."""

    def __init__(
        self, api_key: str, project: str = "artifactor"
    ) -> None:
        self._client: Any = None
        self._api_key = api_key
        self._project = project
        self._active_runs: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "langsmith"

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from langsmith import Client  # type: ignore[import-untyped]

                self._client = Client(api_key=self._api_key)
            except ImportError:
                logger.warning(
                    "event=langsmith_import_failed "
                    "action=install_with pip install artifactor[langsmith]"
                )
                raise
        return self._client  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]

    async def handle(self, event: TraceEvent) -> None:
        """Map pipeline events to LangSmith run hierarchy.

        Stub implementation -- creates client on first use.
        Full run tree mapping deferred until LangSmith is wired end-to-end.
        """
        client = self._ensure_client()

        match event.type:
            case "pipeline_start":
                logger.debug(
                    "event=langsmith_pipeline_start trace_id=%s",
                    event.trace_id,
                )
            case "stage_start":
                stage = event.data.get("stage", "unknown")
                logger.debug(
                    "event=langsmith_stage_start stage=%s",
                    stage,
                )
            case "stage_end":
                stage = event.data.get("stage", "unknown")
                logger.debug(
                    "event=langsmith_stage_end stage=%s",
                    stage,
                )
            case "llm_call":
                logger.debug(
                    "event=langsmith_llm_call model=%s",
                    event.data.get("model", "unknown"),
                )
            case "pipeline_end":
                logger.debug(
                    "event=langsmith_pipeline_end trace_id=%s",
                    event.trace_id,
                )
            case "error":
                logger.debug(
                    "event=langsmith_error component=%s",
                    event.data.get("component", "unknown"),
                )
            case _:
                pass
        # Suppress unused-variable warning for client
        _ = client
