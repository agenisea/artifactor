"""Project lifecycle management service."""

from __future__ import annotations

from typing import Any

from sqlalchemy import update as sa_update

from artifactor.constants import ProjectStatus
from artifactor.models.project import Project
from artifactor.repositories.protocols import ProjectRepository


class ProjectService:
    def __init__(
        self,
        repo: ProjectRepository,
        session_factory: Any = None,
    ) -> None:
        self._repo = repo
        self._session_factory = session_factory

    async def list_all(self) -> list[Project]:
        return await self._repo.list_all()

    async def get(self, project_id: str) -> Project | None:
        return await self._repo.get_by_id(project_id)

    async def create(
        self,
        name: str,
        local_path: str | None = None,
        branch: str | None = None,
    ) -> Project:
        project = Project(
            name=name,
            local_path=local_path,
            branch=branch,
            status=ProjectStatus.PENDING,
        )
        return await self._repo.create(project)

    async def delete(self, project_id: str) -> None:
        await self._repo.delete(project_id)

    async def update_status(
        self, project_id: str, status: str
    ) -> None:
        await self._repo.update_status(project_id, status)

    async def try_set_status(
        self, project_id: str, expected: set[str], new_status: str
    ) -> bool:
        """Atomic CAS: set status only if current is in expected set."""
        return await self._repo.try_set_status(
            project_id, expected, new_status
        )

    # ── Immediate-commit variants for SSE endpoints ──────────
    #
    # SSE generators hold a long-lived dependency session that
    # only commits after the stream ends.  These methods open a
    # dedicated short-lived session so status transitions are
    # visible to other requests immediately.

    async def update_status_immediate(
        self, project_id: str, status: str
    ) -> None:
        """Update status in a dedicated short-lived session.

        Uses raw SQLAlchemy instead of the repository protocol
        because this requires its own session/transaction —
        the caller's session may be long-lived (SSE stream).
        Keeping this in the service avoids leaking session
        lifecycle concerns into the repository protocol.
        """
        if self._session_factory is None:
            await self._repo.update_status(project_id, status)
            return
        async with self._session_factory() as session:
            await session.execute(
                sa_update(Project)
                .where(Project.id == project_id)
                .values(status=status)
            )
            await session.commit()

    async def try_set_status_immediate(
        self, project_id: str, expected: set[str], new_status: str
    ) -> bool:
        """Atomic CAS in a dedicated short-lived session."""
        if self._session_factory is None:
            return await self._repo.try_set_status(
                project_id, expected, new_status
            )
        async with self._session_factory() as session:
            result = await session.execute(
                sa_update(Project)
                .where(
                    Project.id == project_id,
                    Project.status.in_(expected),
                )
                .values(status=new_status)
            )
            await session.commit()
            rowcount: int = (
                getattr(result, "rowcount", 0) or 0
            )
            return rowcount > 0
