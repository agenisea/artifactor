"""SQL implementation of RelationshipRepository."""

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artifactor.models.relationship import Relationship


class SqlRelationshipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_callers(
        self,
        project_id: str,
        file_path: str,
        symbol_name: str,
        depth: int = 1,
    ) -> list[Relationship]:
        # Depth-1 query: find direct callers of target symbol
        result = await self._session.execute(
            select(Relationship).where(
                Relationship.project_id == project_id,
                Relationship.target_file == file_path,
                Relationship.target_symbol == symbol_name,
            )
        )
        return list(result.scalars().all())

    async def get_callees(
        self,
        project_id: str,
        file_path: str,
        symbol_name: str,
        depth: int = 1,
    ) -> list[Relationship]:
        # Depth-1 query: find direct callees of source symbol
        result = await self._session.execute(
            select(Relationship).where(
                Relationship.project_id == project_id,
                Relationship.source_file == file_path,
                Relationship.source_symbol == symbol_name,
            )
        )
        return list(result.scalars().all())

    async def list_by_project(
        self, project_id: str
    ) -> list[Relationship]:
        result = await self._session.execute(
            select(Relationship).where(
                Relationship.project_id == project_id
            )
        )
        return list(result.scalars().all())

    async def bulk_insert(self, relationships: list[Relationship]) -> None:
        self._session.add_all(relationships)
        await self._session.flush()

    async def delete_by_project(self, project_id: str) -> None:
        await self._session.execute(
            sa_delete(Relationship).where(
                Relationship.project_id == project_id
            )
        )
        await self._session.flush()
