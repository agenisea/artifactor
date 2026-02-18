"""SQL implementation of ProjectRepository."""

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from artifactor.models.project import Project


class SqlProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, project_id: str) -> Project | None:
        result = await self._session.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Project]:
        result = await self._session.execute(
            select(Project).order_by(Project.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, project: Project) -> Project:
        self._session.add(project)
        await self._session.flush()
        return project

    async def update_status(self, project_id: str, status: str) -> None:
        project = await self.get_by_id(project_id)
        if project:
            project.status = status
            await self._session.flush()

    async def try_set_status(
        self, project_id: str, expected: set[str], new_status: str
    ) -> bool:
        """Atomically set status only if current status matches expected."""
        result = await self._session.execute(
            sa_update(Project)
            .where(
                Project.id == project_id,
                Project.status.in_(expected),
            )
            .values(status=new_status)
        )
        await self._session.flush()
        rowcount: int = getattr(result, "rowcount", 0) or 0
        return rowcount > 0

    async def delete(self, project_id: str) -> None:
        await self._session.execute(
            sa_delete(Project).where(Project.id == project_id)
        )
        await self._session.flush()
