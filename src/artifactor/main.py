"""FastAPI application with lifespan startup."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

# Phase 1: Singleton logging — MUST be before any artifactor imports
# (they transitively import litellm which reads LITELLM_LOG at import time)
from artifactor.logging_config import setup_logging

setup_logging()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from sqlalchemy import update as sa_update  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: E402

from artifactor.api.app_state import AppState  # noqa: E402
from artifactor.api.event_bus import AnalysisEventBus  # noqa: E402
from artifactor.api.middleware.auth import ApiKeyMiddleware  # noqa: E402
from artifactor.api.routes import (  # noqa: E402
    api_endpoints,
    call_graph,
    chat,
    conversations,
    data_models,
    diagrams,
    entities,
    features,
    filesystem,
    health,
    intelligence,
    playbooks,
    projects,
    sections,
    security,
    user_stories,
)
from artifactor.config import Settings, create_app_engine  # noqa: E402
from artifactor.constants import ProjectStatus  # noqa: E402
from artifactor.logger import AgentLogger  # noqa: E402
from artifactor.logging_config import (  # noqa: E402
    cleanup_third_party_handlers,
)
from artifactor.models.base import Base  # noqa: E402
from artifactor.observability import initialize_tracing  # noqa: E402
from artifactor.resilience.idempotency import (  # noqa: E402
    IdempotencyGuard,
)
from artifactor.services.data_service import DataService  # noqa: E402

# Phase 2: Now that all imports (including litellm) are done,
# clear litellm's duplicate handlers.
cleanup_third_party_handlers()

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 1. Use module-level settings (single source of truth)
    settings = _settings

    # 2. Create async SQLite engine (WAL set via pool-connect listener)
    engine = create_app_engine(
        settings.database_url, echo=settings.debug_mode
    )

    # 3. Create tables + recover stuck analyses
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Recover stuck analyses on startup.
        # event_bus and analysis_tasks are in-memory and non-persistent.
        # Recovery ORM query handles stale DB statuses left by prior crashes.
        from datetime import UTC, datetime, timedelta

        from artifactor.models.project import Project

        cutoff = datetime.now(UTC) - timedelta(
            seconds=settings.analysis_timeout_seconds
        )
        result = await conn.execute(
            sa_update(Project)
            .where(
                Project.status.in_(
                    [
                        ProjectStatus.ANALYZING,
                        ProjectStatus.PAUSED,
                    ]
                ),
                Project.updated_at < cutoff,
            )
            .values(status=ProjectStatus.ERROR)
        )
        if result.rowcount:
            _logger.warning(
                "event=status_recovery recovered=%d",
                result.rowcount,
            )

    # 4. Create session factory
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 5. Initialize logger
    logger = AgentLogger(
        log_dir=settings.log_dir, level=settings.log_level
    )

    # 6. Initialize services
    data_service = DataService(session_factory, settings)

    # 7. Initialize observability
    dispatcher = initialize_tracing(settings)

    # 8. Store in app.state
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.logger = logger
    app.state.data_service = data_service
    app.state.dispatcher = dispatcher
    app.state.idempotency = IdempotencyGuard()
    app.state.event_bus = AnalysisEventBus()
    analysis_tasks: dict[str, asyncio.Task[object]] = {}
    app.state.analysis_tasks = analysis_tasks
    analysis_queues: dict[str, asyncio.Queue[dict[str, str]]] = {}
    app.state.analysis_queues = analysis_queues
    bg_tasks: set[asyncio.Task[None]] = set()
    app.state.background_tasks = bg_tasks

    # Typed state for projects.py (replaces getattr access)
    app.state.typed = AppState(
        settings=settings,
        session_factory=session_factory,
        event_bus=app.state.event_bus,
        idempotency=app.state.idempotency,
        dispatcher=dispatcher,
        analysis_tasks=analysis_tasks,
        analysis_queues=analysis_queues,
        background_tasks=bg_tasks,
    )

    # 9. Security: warn if auth is disabled
    if not settings.api_key:
        _logger.warning(
            "event=no_api_key action=all_endpoints_public"
        )

    yield

    # Cleanup
    await engine.dispose()


app = FastAPI(
    title="Artifactor",
    description=(
        "Code intelligence platform --"
        " turns any codebase into queryable intelligence"
    ),
    version="0.1.0",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Middleware stack (Starlette LIFO: last added = outermost = runs first)
#
# Inbound request order:
#   CORSMiddleware (outermost) -> ApiKeyMiddleware -> Router
#
# CORS must be outermost so OPTIONS preflight is answered before
# ApiKeyMiddleware rejects for missing X-API-Key.
# Always present — empty origins list = no-op passthrough.
_settings = Settings()
_cors_origins = [
    o.strip()
    for o in _settings.cors_origins.split(",")
    if o.strip()
]

app.add_middleware(ApiKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Cache-Control"],
    allow_credentials=False,
)

# Routes
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(sections.router)
app.include_router(intelligence.router)
app.include_router(chat.router)
app.include_router(features.router)
app.include_router(data_models.router)
app.include_router(api_endpoints.router)
app.include_router(user_stories.router)
app.include_router(security.router)
app.include_router(entities.router)
app.include_router(call_graph.router)
app.include_router(diagrams.router)
app.include_router(conversations.router)
app.include_router(playbooks.router)
app.include_router(filesystem.router)
