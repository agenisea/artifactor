"""SQL implementation of CheckpointRepository."""

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from artifactor.models.checkpoint import AnalysisCheckpoint


class SqlCheckpointRepository:
    """Checkpoint repo that owns its own sessions.

    Unlike other repos that receive an ``AsyncSession`` from the route
    handler, checkpoints are written from the LLM analysis pipeline
    (background task) — so we need a session factory to create
    short-lived sessions per operation.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def get(
        self, project_id: str, chunk_hash: str
    ) -> AnalysisCheckpoint | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AnalysisCheckpoint).where(
                    AnalysisCheckpoint.project_id == project_id,
                    AnalysisCheckpoint.chunk_hash == chunk_hash,
                )
            )
            return result.scalar_one_or_none()

    async def put(
        self, checkpoint: AnalysisCheckpoint
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.merge(checkpoint)

    async def count(self, project_id: str) -> int:
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count()).where(
                    AnalysisCheckpoint.project_id == project_id
                )
            )
            return result.scalar_one()

    async def invalidate(self, project_id: str) -> int:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                sa_delete(AnalysisCheckpoint).where(
                    AnalysisCheckpoint.project_id
                    == project_id
                )
            )
            return result.rowcount  # type: ignore[return-value]
