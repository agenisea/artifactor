"""Typed pipeline stages with parallel fan-out support."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from artifactor.constants import StageOutcome

logger = logging.getLogger(__name__)


@dataclass
class StageResult[TOutput]:
    """Outcome of a single pipeline stage execution."""

    stage_name: str
    output: TOutput | None
    duration_ms: float
    status: StageOutcome
    error: str | None = None


@dataclass
class PipelineStage[TInput, TOutput]:
    """A named, typed, async pipeline stage with error isolation."""

    name: str
    execute: Callable[[TInput], Awaitable[TOutput]]

    async def run(
        self, input_data: TInput
    ) -> StageResult[TOutput]:
        """Execute the stage, capturing timing and errors."""
        start = time.monotonic()
        try:
            output = await self.execute(input_data)
            elapsed = (time.monotonic() - start) * 1000
            return StageResult(
                stage_name=self.name,
                output=output,
                duration_ms=elapsed,
                status=StageOutcome.COMPLETED,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.warning(
                "event=stage_failed stage=%s error=%s", self.name, exc
            )
            return StageResult(
                stage_name=self.name,
                output=None,
                duration_ms=elapsed,
                status=StageOutcome.FAILED,
                error=str(exc),
            )


@dataclass
class ParallelGroup[TInput]:
    """Run multiple stages concurrently on the same input."""

    name: str
    stages: list[PipelineStage[TInput, Any]] = field(
        default_factory=lambda: list[PipelineStage[Any, Any]]()
    )
    max_concurrency: int | None = None
    timeout: float | None = None  # seconds; None = no timeout

    async def execute(
        self, input_data: TInput
    ) -> list[StageResult[Any]]:
        """Run all stages concurrently with optional semaphore.

        Every stage runs to completion or failure independently.
        Failed stages do not cancel siblings. If ``timeout`` is set,
        stages still running after the deadline are marked as failed.
        """
        if not self.stages:
            return []

        results: list[StageResult[Any]] = [
            StageResult(
                stage_name=s.name,
                output=None,
                duration_ms=0.0,
                status=StageOutcome.SKIPPED,
            )
            for s in self.stages
        ]

        semaphore = (
            asyncio.Semaphore(self.max_concurrency)
            if self.max_concurrency
            else None
        )

        async def _run_stage(
            idx: int, stage: PipelineStage[TInput, Any]
        ) -> None:
            if semaphore:
                async with semaphore:
                    results[idx] = await stage.run(
                        input_data
                    )
            else:
                results[idx] = await stage.run(input_data)

        tasks = [
            _run_stage(i, stage)
            for i, stage in enumerate(self.stages)
        ]
        coro = asyncio.gather(*tasks, return_exceptions=True)

        if self.timeout is not None:
            try:
                await asyncio.wait_for(coro, timeout=self.timeout)
            except TimeoutError:
                logger.error(
                    "event=parallel_group_timeout group=%s"
                    " timeout_s=%.1f",
                    self.name,
                    self.timeout,
                )
        else:
            await coro

        return results
