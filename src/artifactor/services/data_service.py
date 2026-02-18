"""DB initialization and component health checks."""

import shutil

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from artifactor.config import Settings


class DataService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def check_connection(self) -> bool:
        try:
            async with self._session_factory() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def check_vector_store(self) -> bool:
        try:
            import lancedb

            db = await lancedb.connect_async(self._settings.lancedb_uri)
            await db.list_tables()
            return True
        except Exception:
            return False

    def check_mermaid_cli(self) -> bool:
        return shutil.which("mmdc") is not None
