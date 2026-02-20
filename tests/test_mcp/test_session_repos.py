"""Tests for MCP SessionRepos and cached settings."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from artifactor.mcp.server import configure
from artifactor.mcp.tools import (
    SessionRepos,
    _get_settings,
    _session_repos,
)
from artifactor.models.base import Base
from artifactor.repositories.document_repo import (
    SqlDocumentRepository,
)
from artifactor.repositories.entity_repo import (
    SqlEntityRepository,
)
from artifactor.repositories.relationship_repo import (
    SqlRelationshipRepository,
)


@pytest.fixture
async def configured_session():
    """Configure MCP with in-memory DB for session tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine, expire_on_commit=False
    )
    configure(factory, default_project_id="test-proj")
    yield factory
    await engine.dispose()


class TestSessionRepos:
    def test_named_tuple_attributes(self) -> None:
        """SessionRepos has .entity, .document, .relationship."""
        assert hasattr(SessionRepos, "_fields")
        assert SessionRepos._fields == (
            "entity",
            "document",
            "relationship",
        )

    @pytest.mark.asyncio
    async def test_yields_session_repos_instance(
        self, configured_session: async_sessionmaker
    ) -> None:
        """_session_repos() yields a SessionRepos."""
        async with _session_repos() as repos:
            assert isinstance(repos, SessionRepos)
            assert isinstance(
                repos.entity, SqlEntityRepository
            )
            assert isinstance(
                repos.document, SqlDocumentRepository
            )
            assert isinstance(
                repos.relationship,
                SqlRelationshipRepository,
            )


class TestGetSettings:
    def test_cached_returns_same_instance(self) -> None:
        """Calling _get_settings() twice returns same obj."""
        _get_settings.cache_clear()
        s1 = _get_settings()
        s2 = _get_settings()
        assert s1 is s2
