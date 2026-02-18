"""CRUD tests for SqlEntityRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artifactor.models.entity import CodeEntityRecord
from artifactor.models.project import Project
from artifactor.repositories.entity_repo import (
    SqlEntityRepository,
)


@pytest.fixture
def repo(session: AsyncSession) -> SqlEntityRepository:
    return SqlEntityRepository(session)


@pytest.fixture
async def project_id(session: AsyncSession) -> str:
    p = Project(name="entity-test")
    session.add(p)
    await session.flush()
    return p.id


async def test_bulk_insert_creates_entities(
    repo: SqlEntityRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    entities = [
        CodeEntityRecord(
            project_id=project_id,
            name="UserService",
            entity_type="class",
            file_path="src/user.py",
            start_line=1,
            end_line=50,
        ),
        CodeEntityRecord(
            project_id=project_id,
            name="create_user",
            entity_type="function",
            file_path="src/user.py",
            start_line=10,
            end_line=20,
        ),
    ]
    await repo.bulk_insert(entities)
    await session.commit()

    results = await repo.search(project_id, "user")
    assert len(results) == 2


async def test_search_by_keyword(
    repo: SqlEntityRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    await repo.bulk_insert(
        [
            CodeEntityRecord(
                project_id=project_id,
                name="OrderManager",
                entity_type="class",
                file_path="src/order.py",
                start_line=1,
                end_line=30,
            ),
            CodeEntityRecord(
                project_id=project_id,
                name="PaymentProcessor",
                entity_type="class",
                file_path="src/pay.py",
                start_line=1,
                end_line=40,
            ),
        ]
    )
    await session.commit()

    results = await repo.search(project_id, "Order")
    assert len(results) == 1
    assert results[0].name == "OrderManager"


async def test_search_by_entity_type(
    repo: SqlEntityRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    await repo.bulk_insert(
        [
            CodeEntityRecord(
                project_id=project_id,
                name="get_items",
                entity_type="function",
                file_path="src/api.py",
                start_line=1,
                end_line=10,
            ),
            CodeEntityRecord(
                project_id=project_id,
                name="Item",
                entity_type="class",
                file_path="src/models.py",
                start_line=1,
                end_line=20,
            ),
        ]
    )
    await session.commit()

    funcs = await repo.search(
        project_id, "", entity_type="function"
    )
    assert len(funcs) == 1
    assert funcs[0].name == "get_items"


async def test_get_by_path_returns_file_entities(
    repo: SqlEntityRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    await repo.bulk_insert(
        [
            CodeEntityRecord(
                project_id=project_id,
                name="foo",
                entity_type="function",
                file_path="src/utils.py",
                start_line=1,
                end_line=5,
            ),
            CodeEntityRecord(
                project_id=project_id,
                name="bar",
                entity_type="function",
                file_path="src/utils.py",
                start_line=10,
                end_line=15,
            ),
            CodeEntityRecord(
                project_id=project_id,
                name="baz",
                entity_type="function",
                file_path="src/other.py",
                start_line=1,
                end_line=5,
            ),
        ]
    )
    await session.commit()

    results = await repo.get_by_path(
        project_id, "src/utils.py"
    )
    assert len(results) == 2
    names = {r.name for r in results}
    assert names == {"foo", "bar"}


async def test_search_empty_query(
    repo: SqlEntityRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    await repo.bulk_insert(
        [
            CodeEntityRecord(
                project_id=project_id,
                name="X",
                entity_type="class",
                file_path="x.py",
                start_line=1,
                end_line=1,
            ),
        ]
    )
    await session.commit()

    results = await repo.search(project_id, "")
    assert len(results) >= 1


async def test_get_by_path_wrong_project(
    repo: SqlEntityRepository,
    session: AsyncSession,
) -> None:
    p1 = Project(name="proj-a")
    p2 = Project(name="proj-b")
    session.add_all([p1, p2])
    await session.flush()

    await repo.bulk_insert(
        [
            CodeEntityRecord(
                project_id=p1.id,
                name="only_in_a",
                entity_type="function",
                file_path="a.py",
                start_line=1,
                end_line=1,
            ),
        ]
    )
    await session.commit()

    results = await repo.get_by_path(p2.id, "a.py")
    assert results == []
