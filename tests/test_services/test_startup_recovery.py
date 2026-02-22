"""Tests for startup recovery ORM query (replaces raw SQL)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from artifactor.constants import ProjectStatus
from artifactor.models.base import Base
from artifactor.models.project import Project


@pytest.fixture
async def recovery_engine() -> AsyncEngine:
    """In-memory engine with projects table."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest.mark.asyncio
async def test_recovery_resets_stuck_analyzing(
    recovery_engine: AsyncEngine,
) -> None:
    """Projects stuck in ANALYZING with old updated_at are set to ERROR."""
    session_factory = async_sessionmaker(
        recovery_engine, expire_on_commit=False
    )

    # Insert a project stuck in ANALYZING with old timestamp
    old_time = datetime.now(UTC) - timedelta(seconds=1200)
    async with session_factory() as session:
        project = Project(
            id="stuck-1",
            name="Stuck Project",
            status=ProjectStatus.ANALYZING,
            updated_at=old_time,
        )
        session.add(project)
        await session.commit()

    # Run the same recovery query used in main.py lifespan
    timeout_seconds = 900
    cutoff = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
    async with recovery_engine.begin() as conn:
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
        assert result.rowcount == 1

    # Verify status changed
    async with session_factory() as session:
        row = await session.execute(
            select(Project).where(Project.id == "stuck-1")
        )
        p = row.scalar_one()
        assert p.status == ProjectStatus.ERROR

    await recovery_engine.dispose()


@pytest.mark.asyncio
async def test_recovery_skips_recent(
    recovery_engine: AsyncEngine,
) -> None:
    """Projects with recent updated_at are NOT reset."""
    session_factory = async_sessionmaker(
        recovery_engine, expire_on_commit=False
    )

    # Insert a project in ANALYZING with recent timestamp
    async with session_factory() as session:
        project = Project(
            id="recent-1",
            name="Recent Project",
            status=ProjectStatus.ANALYZING,
            updated_at=datetime.now(UTC),
        )
        session.add(project)
        await session.commit()

    # Run recovery — should NOT touch this project
    timeout_seconds = 900
    cutoff = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
    async with recovery_engine.begin() as conn:
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
        assert result.rowcount == 0

    # Verify status unchanged
    async with session_factory() as session:
        row = await session.execute(
            select(Project).where(Project.id == "recent-1")
        )
        p = row.scalar_one()
        assert p.status == ProjectStatus.ANALYZING

    await recovery_engine.dispose()
