"""CRUD tests for SqlProjectRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artifactor.constants import ProjectStatus
from artifactor.models.project import Project
from artifactor.repositories.project_repo import SqlProjectRepository


@pytest.fixture
def repo(session: AsyncSession) -> SqlProjectRepository:
    return SqlProjectRepository(session)


async def test_create_and_get(
    repo: SqlProjectRepository, session: AsyncSession,
) -> None:
    project = Project(name="test-project", local_path="/tmp/test-repo")
    created = await repo.create(project)
    await session.commit()

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.name == "test-project"
    assert fetched.local_path == "/tmp/test-repo"
    assert fetched.status == ProjectStatus.PENDING


async def test_list_all(
    repo: SqlProjectRepository, session: AsyncSession,
) -> None:
    await repo.create(Project(name="project-a"))
    await repo.create(Project(name="project-b"))
    await session.commit()

    projects = await repo.list_all()
    assert len(projects) == 2


async def test_update_status(
    repo: SqlProjectRepository, session: AsyncSession,
) -> None:
    project = Project(name="status-test")
    created = await repo.create(project)
    await session.commit()

    await repo.update_status(created.id, ProjectStatus.ANALYZING)
    await session.commit()

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.status == ProjectStatus.ANALYZING


async def test_delete(
    repo: SqlProjectRepository, session: AsyncSession,
) -> None:
    project = Project(name="delete-me")
    created = await repo.create(project)
    await session.commit()

    await repo.delete(created.id)
    await session.commit()

    fetched = await repo.get_by_id(created.id)
    assert fetched is None


async def test_get_nonexistent(repo: SqlProjectRepository) -> None:
    fetched = await repo.get_by_id("nonexistent-id")
    assert fetched is None
