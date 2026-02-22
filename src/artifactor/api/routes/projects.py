"""Project CRUD and analysis trigger routes."""

from __future__ import annotations

import asyncio
import functools
import json
import logging
from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from artifactor.api.app_state import AppState
from artifactor.api.dependencies import (
    get_project_service,
)
from artifactor.api.event_bus import AnalysisEventBus
from artifactor.api.schemas import APIResponse, ProjectCreate
from artifactor.constants import (
    SSE_POLL_TIMEOUT,
    ProjectStatus,
    SSEEvent,
)
from artifactor.services.analysis_service import (
    AnalysisResult,
    run_analysis,
)
from artifactor.services.events import StageEvent
from artifactor.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _app_state(request: Request) -> AppState:
    """Typed accessor for application state."""
    state: AppState = request.app.state.typed
    return state


async def _cas_set_status(
    service: ProjectService,
    project_id: str,
    new_status: str,
) -> None:
    """CAS status update: only overwrite if still ANALYZING.

    Delegates to ProjectService.try_set_status_immediate which owns
    the short-lived session + CAS pattern.
    """
    try:
        await service.try_set_status_immediate(
            project_id,
            {ProjectStatus.ANALYZING},
            new_status,
        )
    except Exception:
        logger.exception(
            "event=done_callback_failed project_id=%s",
            project_id,
        )


# -- SSE event builders --


def _error_event(message: str) -> dict[str, str]:
    """Build an SSE error event dict."""
    return {
        "event": SSEEvent.ERROR,
        "data": json.dumps({"error": message}),
    }


def _stage_event(event: StageEvent) -> dict[str, str]:
    """Build an SSE stage event dict from a StageEvent."""
    payload: dict[str, object] = {
        "name": event.name,
        "label": event.label,
        "status": event.status,
        "message": event.message,
        "duration_ms": event.duration_ms,
    }
    if event.completed is not None:
        payload["completed"] = event.completed
        payload["total"] = event.total
        payload["percent"] = event.percent
    return {
        "event": SSEEvent.STAGE,
        "data": json.dumps(payload),
    }


def _complete_event(
    project_id: str,
    result: AnalysisResult,
) -> dict[str, str]:
    """Build an SSE complete event dict."""
    return {
        "event": SSEEvent.COMPLETE,
        "data": json.dumps(
            {
                "project_id": project_id,
                "sections": len(result.sections),
                "stages_ok": sum(
                    1 for s in result.stages if s.ok
                ),
                "stages_failed": sum(
                    1
                    for s in result.stages
                    if not s.ok
                ),
                "partial": any(
                    not s.ok for s in result.stages
                ),
                "duration_ms": result.total_duration_ms,
            }
        ),
    }


def _paused_event() -> dict[str, str]:
    """Build an SSE paused event dict."""
    return {
        "event": SSEEvent.PAUSED,
        "data": json.dumps({"message": "Analysis paused"}),
    }


# -- Stream helpers --


async def _late_joiner_stream(
    event_bus: AnalysisEventBus,
    project_id: str,
) -> AsyncIterator[dict[str, str]]:
    """Subscribe to an existing analysis channel and yield events."""
    queue = await event_bus.subscribe(project_id)
    while True:
        event = await queue.get()
        if event is None:
            break
        yield event


async def _drain_events(
    event_queue: asyncio.Queue[dict[str, str]],
    analysis_task: asyncio.Task[AnalysisResult],
) -> AsyncIterator[dict[str, str]]:
    """Drain SSE events from the queue until the task completes."""
    while not analysis_task.done() or not event_queue.empty():
        try:
            event_dict = await asyncio.wait_for(
                event_queue.get(),
                timeout=SSE_POLL_TIMEOUT,
            )
            yield event_dict
        except TimeoutError:
            continue


# -- Task lifecycle --


async def _create_and_register_task(
    state: AppState,
    project_id: str,
    repo_path: str,
    branch: str,
    on_progress: Callable[[StageEvent], None],
) -> asyncio.Task[AnalysisResult]:
    """Create analysis background task and register it in app state.

    Wraps with IdempotencyGuard. Registers the task in
    ``state.analysis_tasks`` and creates an event bus channel.
    """

    async def _run() -> AnalysisResult:
        return await run_analysis(
            repo_path=repo_path,
            settings=state.settings,
            branch=branch,
            on_progress=on_progress,
            dispatcher=state.dispatcher,
            session_factory=state.session_factory,
            project_id=project_id,
        )

    task = asyncio.create_task(
        state.idempotency.execute(
            f"analyze:{project_id}", _run
        )
    )
    await state.event_bus.create_channel(project_id)
    state.analysis_tasks[project_id] = task
    return task


def _on_analysis_done(
    task: asyncio.Task[AnalysisResult],
    *,
    project_id: str,
    analysis_tasks: dict[str, asyncio.Task[object]],
    service: ProjectService | None,
    event_bus: AnalysisEventBus,
    bg_tasks: set[asyncio.Task[None]],
) -> None:
    """Safety-net callback: update status + clean up on task completion."""
    analysis_tasks.pop(project_id, None)

    # Log exception *before* the async work -- task.exception() is
    # cheap and synchronous here, and we may never reach the async
    # path if the event loop is shutting down.
    exc = (
        task.exception() if not task.cancelled() else None
    )
    if task.cancelled():
        logger.warning(
            "event=analysis_cancelled project_id=%s",
            project_id,
        )
    elif exc is not None:
        logger.error(
            "event=analysis_exception project_id=%s",
            project_id,
            exc_info=exc,
        )

    async def _set_status() -> None:
        if service is None:
            await event_bus.complete(project_id)
            return
        status = (
            ProjectStatus.ERROR
            if task.cancelled() or exc is not None
            else ProjectStatus.ANALYZED
        )
        await _cas_set_status(service, project_id, status)
        await event_bus.complete(project_id)

    t = asyncio.create_task(_set_status())
    bg_tasks.add(t)
    t.add_done_callback(bg_tasks.discard)


# -- Route handlers --


@router.get("")
async def list_projects(
    service: ProjectService = Depends(get_project_service),
) -> APIResponse:
    """List all analyzed projects."""
    projects = await service.list_all()
    return APIResponse(
        success=True,
        data=[p.to_dict() for p in projects],
    )


@router.post("")
async def create_project(
    body: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
) -> APIResponse:
    """Create a new project."""
    project = await service.create(
        name=body.name,
        local_path=body.local_path,
        branch=body.branch,
    )
    return APIResponse(success=True, data=project.to_dict())


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> APIResponse:
    """Get project metadata and analysis status."""
    project = await service.get(project_id)
    if project is None:
        return APIResponse(
            success=False, error="Project not found"
        )
    return APIResponse(success=True, data=project.to_dict())


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> APIResponse:
    """Delete a project and all associated data."""
    await service.delete(project_id)
    return APIResponse(success=True)


@router.post("/{project_id}/analyze")
async def analyze_project(
    request: Request,
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> EventSourceResponse:
    """Trigger analysis with SSE progress streaming."""
    return EventSourceResponse(
        _analyze_event_stream(request, project_id, service),
        sep="\n",
    )


async def _analyze_event_stream(
    request: Request,
    project_id: str,
    service: ProjectService,
) -> AsyncIterator[dict[str, str]]:
    """Async generator yielding SSE events during analysis.

    If analysis is already running, subscribes to the existing
    event bus channel (late-joiner path) instead of failing.
    """
    state = _app_state(request)

    project = await service.get(project_id)
    if project is None:
        yield _error_event("Project not found")
        return

    # Atomic CAS: only one analyze request can proceed.
    # PAUSED is included so "Resume" works.
    acquired = await service.try_set_status_immediate(
        project_id,
        {
            ProjectStatus.PENDING,
            ProjectStatus.ERROR,
            ProjectStatus.ANALYZED,
            ProjectStatus.PAUSED,
        },
        ProjectStatus.ANALYZING,
    )

    # Late-joiner path
    if not acquired:
        if state.event_bus.has_channel(project_id):
            async for event in _late_joiner_stream(
                state.event_bus, project_id
            ):
                yield event
            return
        yield _error_event("Analysis already in progress")
        return

    # Primary path: setup + run
    event_queue: asyncio.Queue[dict[str, str]] = (
        asyncio.Queue()
    )

    def on_progress(event: StageEvent) -> None:
        event_dict = _stage_event(event)
        event_queue.put_nowait(event_dict)
        state.event_bus.publish(project_id, event_dict)

    analysis_task = await _create_and_register_task(
        state,
        project_id,
        project.local_path or "",
        project.branch or "main",
        on_progress,
    )
    state.analysis_queues[project_id] = event_queue

    analysis_task.add_done_callback(
        functools.partial(
            _on_analysis_done,
            project_id=project_id,
            analysis_tasks=state.analysis_tasks,
            service=service,
            event_bus=state.event_bus,
            bg_tasks=state.background_tasks,
        )
    )

    # Drain events
    async for event in _drain_events(
        event_queue, analysis_task
    ):
        yield event

    state.analysis_queues.pop(project_id, None)

    # Result
    try:
        result = await analysis_task
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception(
            "event=analysis_failed project_id=%s",
            project_id,
        )
        error = _error_event(
            "Analysis failed."
            " Check server logs for details."
        )
        state.event_bus.publish(project_id, error)
        yield error
        return

    complete = _complete_event(project_id, result)
    state.event_bus.publish(project_id, complete)
    yield complete


@router.post("/{project_id}/pause")
async def pause_project(
    request: Request,
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> APIResponse:
    """Pause a running analysis."""
    project = await service.get(project_id)
    if project is None:
        return APIResponse(
            success=False, error="Project not found"
        )

    acquired = await service.try_set_status_immediate(
        project_id,
        {ProjectStatus.ANALYZING},
        ProjectStatus.PAUSED,
    )
    if not acquired:
        return APIResponse(
            success=False,
            error=(
                f"Cannot pause project in"
                f" '{project.status}' state"
            ),
        )

    state = _app_state(request)
    paused = _paused_event()

    # Deliver paused event to original SSE connection
    # BEFORE cancelling the task (ordering matters).
    queue = state.analysis_queues.get(project_id)
    if queue is not None:
        queue.put_nowait(paused)

    # Cancel the running task
    task = state.analysis_tasks.pop(project_id, None)
    if task is not None and not task.done():
        task.cancel()

    # Publish PAUSED event to event bus (late-joiners)
    # + complete channel
    state.event_bus.publish(project_id, paused)
    await state.event_bus.complete(project_id)

    return APIResponse(
        success=True,
        data={"status": ProjectStatus.PAUSED},
    )


def _derive_stages(
    events: list[dict[str, str]],
) -> list[dict[str, object]]:
    """Extract latest state per pipeline stage from raw SSE events.

    Filters for ``event == "stage"`` entries, parses their JSON ``data``,
    and keeps only the most recent event per stage ``name`` (last-write-wins).
    Returns a list of stage snapshots ordered by first appearance.
    """
    latest: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for ev in events:
        if ev.get("event") != SSEEvent.STAGE:
            continue
        try:
            payload: dict[str, object] = json.loads(
                ev["data"]
            )
        except (json.JSONDecodeError, KeyError):
            continue
        name = str(payload.get("name", ""))
        if not name:
            continue
        if name not in latest:
            order.append(name)
        latest[name] = {
            "name": name,
            "label": payload.get("label", ""),
            "status": payload.get("status", ""),
            "message": payload.get("message", ""),
            "duration_ms": payload.get("duration_ms", 0.0),
            "completed": payload.get("completed"),
            "total": payload.get("total"),
            "percent": payload.get("percent"),
        }
    return [latest[n] for n in order]


@router.get("/{project_id}/status")
async def get_analysis_status(
    request: Request,
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> APIResponse:
    """Get current analysis progress for a project."""
    project = await service.get(project_id)
    if project is None:
        return APIResponse(
            success=False, error="Project not found"
        )
    data: dict[str, object] = {
        "project_id": project_id,
        "status": project.status,
    }
    state = _app_state(request)
    if project.status == ProjectStatus.ANALYZING:
        raw_events = state.event_bus.get_latest_events(
            project_id
        )
        stages = _derive_stages(raw_events)
        if stages:
            data["stages"] = stages
    return APIResponse(success=True, data=data)
