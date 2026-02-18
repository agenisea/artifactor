"""CRUD tests for SqlDocumentRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artifactor.models.document import Document
from artifactor.models.project import Project
from artifactor.repositories.document_repo import (
    SqlDocumentRepository,
)


@pytest.fixture
def repo(session: AsyncSession) -> SqlDocumentRepository:
    return SqlDocumentRepository(session)


@pytest.fixture
async def project_id(session: AsyncSession) -> str:
    p = Project(name="doc-test")
    session.add(p)
    await session.flush()
    return p.id


async def test_upsert_section_creates_new(
    repo: SqlDocumentRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    doc = Document(
        project_id=project_id,
        section_name="features",
        content="# Features",
        confidence=0.9,
    )
    result = await repo.upsert_section(doc)
    await session.commit()
    assert result.section_name == "features"
    assert result.content == "# Features"


async def test_upsert_section_updates_existing(
    repo: SqlDocumentRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    doc1 = Document(
        project_id=project_id,
        section_name="features",
        content="v1",
        confidence=0.5,
    )
    await repo.upsert_section(doc1)
    await session.commit()

    doc2 = Document(
        project_id=project_id,
        section_name="features",
        content="v2",
        confidence=0.9,
    )
    result = await repo.upsert_section(doc2)
    await session.commit()
    assert result.content == "v2"
    assert result.confidence == 0.9


async def test_get_section_returns_none_when_missing(
    repo: SqlDocumentRepository,
    project_id: str,
) -> None:
    result = await repo.get_section(
        project_id, "nonexistent"
    )
    assert result is None


async def test_list_sections_returns_all(
    repo: SqlDocumentRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    await repo.upsert_section(
        Document(
            project_id=project_id,
            section_name="features",
            content="f",
        )
    )
    await repo.upsert_section(
        Document(
            project_id=project_id,
            section_name="personas",
            content="p",
        )
    )
    await session.commit()
    sections = await repo.list_sections(project_id)
    assert len(sections) == 2
    names = {s.section_name for s in sections}
    assert names == {"features", "personas"}


async def test_list_sections_empty_project(
    repo: SqlDocumentRepository,
    project_id: str,
) -> None:
    sections = await repo.list_sections(project_id)
    assert sections == []


async def test_get_section_correct_project_isolation(
    repo: SqlDocumentRepository,
    session: AsyncSession,
) -> None:
    p1 = Project(name="proj-a")
    p2 = Project(name="proj-b")
    session.add_all([p1, p2])
    await session.flush()

    await repo.upsert_section(
        Document(
            project_id=p1.id,
            section_name="features",
            content="A features",
        )
    )
    await session.commit()

    # Project B should not see A's section
    result = await repo.get_section(
        p2.id, "features"
    )
    assert result is None
