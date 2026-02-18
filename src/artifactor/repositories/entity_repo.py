"""SQL implementation of EntityRepository."""

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artifactor.models.entity import CodeEntityRecord


class SqlEntityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        project_id: str,
        query: str,
        entity_type: str | None = None,
    ) -> list[CodeEntityRecord]:
        stmt = select(CodeEntityRecord).where(
            CodeEntityRecord.project_id == project_id,
            CodeEntityRecord.name.contains(query),
        )
        if entity_type:
            stmt = stmt.where(CodeEntityRecord.entity_type == entity_type)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_path(
        self, project_id: str, file_path: str
    ) -> list[CodeEntityRecord]:
        result = await self._session.execute(
            select(CodeEntityRecord).where(
                CodeEntityRecord.project_id == project_id,
                CodeEntityRecord.file_path == file_path,
            )
        )
        return list(result.scalars().all())

    async def bulk_insert(self, entities: list[CodeEntityRecord]) -> None:
        self._session.add_all(entities)
        await self._session.flush()

    async def delete_by_project(self, project_id: str) -> None:
        await self._session.execute(
            sa_delete(CodeEntityRecord).where(
                CodeEntityRecord.project_id == project_id
            )
        )
        await self._session.flush()
