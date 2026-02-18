"""CRUD tests for SqlRelationshipRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artifactor.constants import RelationshipType
from artifactor.models.project import Project
from artifactor.models.relationship import Relationship
from artifactor.repositories.relationship_repo import (
    SqlRelationshipRepository,
)


@pytest.fixture
def repo(
    session: AsyncSession,
) -> SqlRelationshipRepository:
    return SqlRelationshipRepository(session)


@pytest.fixture
async def project_id(session: AsyncSession) -> str:
    p = Project(name="rel-test")
    session.add(p)
    await session.flush()
    return p.id


async def test_bulk_insert_relationships(
    repo: SqlRelationshipRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    rels = [
        Relationship(
            project_id=project_id,
            source_file="a.py",
            source_symbol="foo",
            target_file="b.py",
            target_symbol="bar",
            relationship_type=RelationshipType.CALLS,
        ),
        Relationship(
            project_id=project_id,
            source_file="a.py",
            source_symbol="foo",
            target_file="c.py",
            target_symbol="baz",
            relationship_type=RelationshipType.IMPORTS,
        ),
    ]
    await repo.bulk_insert(rels)
    await session.commit()

    callees = await repo.get_callees(
        project_id, "a.py", "foo"
    )
    assert len(callees) == 2


async def test_get_callers(
    repo: SqlRelationshipRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    await repo.bulk_insert(
        [
            Relationship(
                project_id=project_id,
                source_file="caller.py",
                source_symbol="do_thing",
                target_file="target.py",
                target_symbol="handle",
                relationship_type=RelationshipType.CALLS,
            ),
        ]
    )
    await session.commit()

    callers = await repo.get_callers(
        project_id, "target.py", "handle"
    )
    assert len(callers) == 1
    assert callers[0].source_symbol == "do_thing"


async def test_get_callees(
    repo: SqlRelationshipRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    await repo.bulk_insert(
        [
            Relationship(
                project_id=project_id,
                source_file="src.py",
                source_symbol="main",
                target_file="lib.py",
                target_symbol="helper",
                relationship_type=RelationshipType.CALLS,
            ),
        ]
    )
    await session.commit()

    callees = await repo.get_callees(
        project_id, "src.py", "main"
    )
    assert len(callees) == 1
    assert callees[0].target_symbol == "helper"


async def test_get_callers_no_results(
    repo: SqlRelationshipRepository,
    project_id: str,
) -> None:
    callers = await repo.get_callers(
        project_id, "none.py", "nothing"
    )
    assert callers == []


async def test_relationships_project_isolation(
    repo: SqlRelationshipRepository,
    session: AsyncSession,
) -> None:
    p1 = Project(name="iso-a")
    p2 = Project(name="iso-b")
    session.add_all([p1, p2])
    await session.flush()

    await repo.bulk_insert(
        [
            Relationship(
                project_id=p1.id,
                source_file="a.py",
                source_symbol="x",
                target_file="b.py",
                target_symbol="y",
                relationship_type=RelationshipType.CALLS,
            ),
        ]
    )
    await session.commit()

    # Project B should see nothing
    result = await repo.get_callees(
        p2.id, "a.py", "x"
    )
    assert result == []
