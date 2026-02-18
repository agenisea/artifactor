"""Typed convenience functions for emitting trace events."""

from __future__ import annotations

from artifactor.observability.dispatcher import TraceDispatcher
from artifactor.observability.events import TraceCategory, TraceEvent


async def emit_pipeline_start(
    dispatcher: TraceDispatcher,
    trace_id: str,
    project_id: str,
) -> None:
    await dispatcher.emit(
        TraceEvent(
            type="pipeline_start",
            trace_id=trace_id,
            category="pipeline",
            data={"project_id": project_id},
        )
    )


async def emit_pipeline_end(
    dispatcher: TraceDispatcher,
    trace_id: str,
    duration_ms: float,
    success: bool,
) -> None:
    await dispatcher.emit(
        TraceEvent(
            type="pipeline_end",
            trace_id=trace_id,
            category="pipeline",
            data={
                "duration_ms": duration_ms,
                "success": success,
            },
        )
    )


async def emit_stage_start(
    dispatcher: TraceDispatcher,
    trace_id: str,
    stage: str,
    category: TraceCategory = "pipeline",
) -> None:
    await dispatcher.emit(
        TraceEvent(
            type="stage_start",
            trace_id=trace_id,
            category=category,
            data={"stage": stage},
        )
    )


async def emit_stage_end(
    dispatcher: TraceDispatcher,
    trace_id: str,
    stage: str,
    duration_ms: float,
    ok: bool,
    error: str | None = None,
) -> None:
    await dispatcher.emit(
        TraceEvent(
            type="stage_end",
            trace_id=trace_id,
            category="pipeline",
            data={
                "stage": stage,
                "duration_ms": duration_ms,
                "ok": ok,
                "error": error,
            },
        )
    )


async def emit_llm_call(
    dispatcher: TraceDispatcher,
    trace_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
    cost: float,
) -> None:
    await dispatcher.emit(
        TraceEvent(
            type="llm_call",
            trace_id=trace_id,
            category="llm",
            data={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "duration_ms": duration_ms,
                "cost": cost,
            },
        )
    )


async def emit_error(
    dispatcher: TraceDispatcher,
    trace_id: str,
    component: str,
    message: str,
) -> None:
    await dispatcher.emit(
        TraceEvent(
            type="error",
            trace_id=trace_id,
            category="pipeline",
            data={
                "component": component,
                "message": message,
            },
        )
    )
