"""Shared test fixtures — in-memory SQLite, async session."""

import os

# Force demo API keys for all tests — no real LLM calls.
# These are set unconditionally at import time, so even if you have
# real keys in your shell environment, pytest overwrites them before
# any Settings() is created. To use real keys, edit these lines.
os.environ["ANTHROPIC_API_KEY"] = "for-demo-purposes-only"
os.environ["OPENAI_API_KEY"] = "for-demo-purposes-only"

from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

from artifactor.api.dependencies import (
    Repos,
    get_data_service,
    get_project_service,
    get_repos,
)
from artifactor.config import Settings
from artifactor.logger import AgentLogger
from artifactor.main import app
from artifactor.models.base import Base
from artifactor.repositories.fakes import (
    FakeConversationRepository,
    FakeDataService,
    FakeDocumentRepository,
    FakeEntityRepository,
    FakeProjectRepository,
    FakeProjectService,
    FakeRelationshipRepository,
)


def setup_test_app(
    tmp_path: Path,
    *,
    agent_model: Any = None,
) -> tuple[Repos, FakeProjectService]:
    """Common app-state setup for API test fixtures.

    Sets up fake repos, settings, logger, project_service, and
    dependency overrides. Each test file's fixture calls this
    then adds its own specifics (e.g. seeded data).

    Returns (repos, project_service) so the fixture can access them.
    """
    fake_project_repo = FakeProjectRepository()
    fake_repos = Repos(
        project=fake_project_repo,
        document=FakeDocumentRepository(),
        entity=FakeEntityRepository(),
        relationship=FakeRelationshipRepository(),
        conversation=FakeConversationRepository(),
    )
    fake_project_service = FakeProjectService(fake_project_repo)

    app.state.settings = Settings(
        database_url="sqlite:///:memory:"
    )
    app.state.logger = AgentLogger(
        log_dir=Path(tmp_path / "logs"), level="WARNING"
    )
    app.state.project_service = fake_project_service
    if agent_model is not None:
        app.state.agent_model = agent_model

    app.dependency_overrides[get_repos] = lambda: fake_repos
    app.dependency_overrides[get_project_service] = (
        lambda: fake_project_service
    )
    app.dependency_overrides[get_data_service] = (
        lambda: FakeDataService()
    )

    return fake_repos, fake_project_service


def parse_sse_events(
    raw: str,
) -> list[dict[str, str]]:
    """Parse raw SSE text into list of {event, data} dicts.

    Shared helper used by SSE endpoint tests.
    """
    events: list[dict[str, str]] = []
    current_event = ""
    current_data = ""

    for line in raw.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:"):
            current_data = line[5:].strip()
        elif line == "" and current_event:
            events.append(
                {"event": current_event, "data": current_data}
            )
            current_event = ""
            current_data = ""

    # Handle trailing event without final blank line
    if current_event and current_data:
        events.append(
            {"event": current_event, "data": current_data}
        )

    return events


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine():
    """Session-scoped engine — one CREATE TABLE per test suite."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine):
    """Function-scoped session with connection-level rollback.

    Wraps each test in a connection-level transaction so that
    even ``session.commit()`` calls inside tests are rolled
    back at teardown, keeping the shared engine clean.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False
        )
        yield session
        await session.close()
        await transaction.rollback()
