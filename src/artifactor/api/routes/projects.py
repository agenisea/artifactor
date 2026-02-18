"""Project CRUD and analysis trigger routes."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sqlalchemy import update as sa_update
from sse_starlette.sse import EventSourceResponse

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
from artifactor.models.project import Project
from artifactor.resilience.idempotency import (
    IdempotencyGuard,
)
from artifactor.services.analysis_service import (
    AnalysisResult,
    StageEvent,
    run_analysis,
)
from artifactor.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


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
    settings = request.app.state.settings

    project = await service.get(project_id)
    if project is None:
        yield {
            "event": SSEEvent.ERROR,
            "data": json.dumps(
                {"error": "Project not found"}
            ),
        }
        return

    event_bus: AnalysisEventBus | None = getattr(
        request.app.state, "event_bus", None
    )
    analysis_tasks: dict[str, asyncio.Task[object]] | None = (
        getattr(request.app.state, "analysis_tasks", None)
    )
    analysis_queues: (
        dict[str, asyncio.Queue[dict[str, str]]] | None
    ) = getattr(request.app.state, "analysis_queues", None)

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

    # Late-joiner path: subscribe to existing event bus channel
    if not acquired:
        if (
            event_bus is not None
            and event_bus.has_channel(project_id)
        ):
            queue = await event_bus.subscribe(project_id)
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
            return
        yield {
            "event": SSEEvent.ERROR,
            "data": json.dumps(
                {"error": "Analysis already in progress"}
            ),
        }
        return

    # Queue-based progress: on_progress converts StageEvents to
    # SSE dicts and publishes to event bus for late-joiners.
    event_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()

    def on_progress(event: StageEvent) -> None:
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
        event_dict: dict[str, str] = {
            "event": SSEEvent.STAGE,
            "data": json.dumps(payload),
        }
        event_queue.put_nowait(event_dict)
        if event_bus is not None:
            event_bus.publish(project_id, event_dict)

    # Run analysis in a background task
    repo_path = project.local_path or ""
    dispatcher = getattr(
        request.app.state, "dispatcher", None
    )
    session_factory = getattr(
        request.app.state, "session_factory", None
    )
    guard: IdempotencyGuard | None = getattr(
        request.app.state, "idempotency", None
    )

    async def _run() -> AnalysisResult:
        return await run_analysis(
            repo_path=repo_path,
            settings=settings,
            branch=project.branch or "main",
            on_progress=on_progress,
            dispatcher=dispatcher,
            session_factory=session_factory,
            project_id=project_id,
        )

    if guard is not None:
        analysis_task = asyncio.create_task(
            guard.execute(
                f"analyze:{project_id}", _run
            )
        )
    else:
        analysis_task = asyncio.create_task(_run())

    # Register task, queue, + create event bus channel
    if event_bus is not None:
        await event_bus.create_channel(project_id)
    if analysis_tasks is not None:
        analysis_tasks[project_id] = analysis_task
    if analysis_queues is not None:
        analysis_queues[project_id] = event_queue

    # Safety net: guarantee status update even if client disconnects
    # and the SSE generator is cancelled. Uses CAS so pause status
    # is not overwritten. Pop from task registry
    # synchronously to avoid stale-reference window.
    bg_tasks: set[asyncio.Task[None]] = getattr(
        request.app.state, "background_tasks", set()
    )

    def _on_analysis_done(
        task: asyncio.Task[AnalysisResult],
    ) -> None:
        # Synchronous pop from task registry
        if analysis_tasks is not None:
            analysis_tasks.pop(project_id, None)

        async def _set_status() -> None:
            if session_factory is None:
                if event_bus is not None:
                    await event_bus.complete(project_id)
                return
            if task.cancelled() or task.exception() is not None:
                # CAS: only overwrite if still ANALYZING
                try:
                    async with session_factory() as session:
                        await session.execute(
                            sa_update(Project)
                            .where(
                                Project.id == project_id,
                                Project.status
                                == ProjectStatus.ANALYZING,
                            )
                            .values(status=ProjectStatus.ERROR)
                        )
                        await session.commit()
                except Exception:
                    logger.exception(
                        "event=done_callback_failed"
                        " project_id=%s",
                        project_id,
                    )
            else:
                # CAS: only overwrite if still ANALYZING
                try:
                    async with session_factory() as session:
                        await session.execute(
                            sa_update(Project)
                            .where(
                                Project.id == project_id,
                                Project.status
                                == ProjectStatus.ANALYZING,
                            )
                            .values(
                                status=ProjectStatus.ANALYZED
                            )
                        )
                        await session.commit()
                except Exception:
                    logger.exception(
                        "event=done_callback_failed"
                        " project_id=%s",
                        project_id,
                    )
            if event_bus is not None:
                await event_bus.complete(project_id)

        t = asyncio.create_task(_set_status())
        bg_tasks.add(t)
        t.add_done_callback(bg_tasks.discard)

    analysis_task.add_done_callback(_on_analysis_done)

    # Drain stage events from the queue (already converted by
    # on_progress and published to event bus for late-joiners).
    while not analysis_task.done() or not event_queue.empty():
        try:
            event_dict = await asyncio.wait_for(
                event_queue.get(),
                timeout=SSE_POLL_TIMEOUT,
            )
            yield event_dict
        except TimeoutError:
            continue

    # Clean up queue registry
    if analysis_queues is not None:
        analysis_queues.pop(project_id, None)

    # Get the result
    try:
        result = await analysis_task
    except asyncio.CancelledError:
        # Pause endpoint already published PAUSED +
        # completed channel. _on_analysis_done handles cleanup.
        return
    except Exception:
        logger.exception(
            "event=analysis_failed project_id=%s",
            project_id,
        )
        error_dict = {
            "event": SSEEvent.ERROR,
            "data": json.dumps(
                {
                    "error": "Analysis failed."
                    " Check server logs for details.",
                }
            ),
        }
        # Publish before yield to avoid race with
        # _on_analysis_done completing the channel.
        if event_bus is not None:
            event_bus.publish(project_id, error_dict)
        yield error_dict
        return

    complete_dict = {
        "event": SSEEvent.COMPLETE,
        "data": json.dumps(
            {
                "project_id": project_id,
                "sections": len(result.sections),
                "stages_ok": sum(
                    1
                    for s in result.stages
                    if s.ok
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
    # Publish before yield to avoid race with
    # _on_analysis_done completing the channel.
    if event_bus is not None:
        event_bus.publish(project_id, complete_dict)
    yield complete_dict


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

    # CAS: only pause if currently ANALYZING
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

    paused_event: dict[str, str] = {
        "event": SSEEvent.PAUSED,
        "data": json.dumps(
            {"message": "Analysis paused"}
        ),
    }

    # Deliver paused event to original SSE connection
    # BEFORE cancelling the task (ordering matters).
    analysis_queues: (
        dict[str, asyncio.Queue[dict[str, str]]] | None
    ) = getattr(request.app.state, "analysis_queues", None)
    if analysis_queues is not None:
        queue = analysis_queues.get(project_id)
        if queue is not None:
            queue.put_nowait(paused_event)

    # Cancel the running task
    analysis_tasks: dict[str, asyncio.Task[object]] | None = (
        getattr(request.app.state, "analysis_tasks", None)
    )
    if analysis_tasks is not None:
        task = analysis_tasks.pop(project_id, None)
        if task is not None and not task.done():
            task.cancel()

    # Publish PAUSED event to event bus (late-joiners)
    # + complete channel
    event_bus: AnalysisEventBus | None = getattr(
        request.app.state, "event_bus", None
    )
    if event_bus is not None:
        event_bus.publish(project_id, paused_event)
        await event_bus.complete(project_id)

    return APIResponse(
        success=True,
        data={"status": ProjectStatus.PAUSED},
    )


@router.get("/{project_id}/status")
async def get_analysis_status(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> APIResponse:
    """Get current analysis progress for a project."""
    project = await service.get(project_id)
    if project is None:
        return APIResponse(
            success=False, error="Project not found"
        )
    return APIResponse(
        success=True,
        data={
            "project_id": project_id,
            "status": project.status,
        },
    )
