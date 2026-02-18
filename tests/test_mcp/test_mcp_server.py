"""Tests for the MCP server."""

from __future__ import annotations

import pytest
from fastmcp import Client
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from artifactor.constants import ProjectStatus
from artifactor.mcp.server import (
    configure,
    get_default_project_id,
    get_session_factory,
    mcp,
)
from artifactor.models.base import Base
from artifactor.models.document import Document
from artifactor.models.entity import CodeEntityRecord
from artifactor.models.project import Project

PROJECT_ID = "test-mcp-proj"


@pytest.fixture
async def mcp_configured():
    """Configure MCP server with in-memory DB."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine, expire_on_commit=False
    )

    # Seed data
    session = factory()
    project = Project(
        id=PROJECT_ID,
        name="MCP Test Project",
        status=ProjectStatus.ANALYZED,
    )
    session.add(project)

    entity = CodeEntityRecord(
        project_id=PROJECT_ID,
        name="McpHandler",
        entity_type="class",
        file_path="src/mcp.py",
        start_line=1,
        end_line=20,
        language="python",
    )
    session.add(entity)

    docs = [
        Document(
            project_id=PROJECT_ID,
            section_name="executive_overview",
            content="This is an MCP test project.",
            confidence=0.9,
        ),
        Document(
            project_id=PROJECT_ID,
            section_name="features",
            content="- MCP integration\n- Tool calling",
            confidence=0.85,
        ),
        Document(
            project_id=PROJECT_ID,
            section_name="system_overview",
            content="Architecture overview here.",
            confidence=0.8,
        ),
        Document(
            project_id=PROJECT_ID,
            section_name="user_stories",
            content="As a dev, I want tools.",
            confidence=0.8,
        ),
        Document(
            project_id=PROJECT_ID,
            section_name="data_models",
            content="Entity-relationship model.",
            confidence=0.8,
        ),
        Document(
            project_id=PROJECT_ID,
            section_name="security_considerations",
            content="Input validation required.",
            confidence=0.7,
        ),
    ]
    session.add_all(docs)
    await session.commit()
    await session.close()

    configure(factory, default_project_id=PROJECT_ID)
    yield factory, engine

    await engine.dispose()


class TestServerConfiguration:
    def test_configure_sets_factory(
        self, mcp_configured
    ) -> None:
        factory = get_session_factory()
        assert factory is not None

    def test_default_project_id(
        self, mcp_configured
    ) -> None:
        pid = get_default_project_id()
        assert pid == PROJECT_ID

    def test_unconfigured_raises(self) -> None:
        from artifactor.mcp import server

        original = server._session_factory
        server._session_factory = None
        with pytest.raises(
            RuntimeError, match="not configured"
        ):
            get_session_factory()
        server._session_factory = original


class TestMcpTools:
    @pytest.mark.asyncio
    async def test_list_tools(
        self, mcp_configured
    ) -> None:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool_names = {t.name for t in tools}
            expected = {
                "query_codebase",
                "get_specification",
                "list_features",
                "get_data_model",
                "explain_symbol",
                "get_call_graph",
                "get_user_stories",
                "get_api_endpoints",
                "search_code_entities",
                "get_security_findings",
            }
            assert expected == tool_names

    @pytest.mark.asyncio
    async def test_get_specification(
        self, mcp_configured
    ) -> None:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_specification",
                {"section": "features"},
            )
            text = result.content[0].text  # type: ignore[union-attr]
            assert "MCP integration" in text

    @pytest.mark.asyncio
    async def test_list_features(
        self, mcp_configured
    ) -> None:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "list_features", {}
            )
            text = result.content[0].text  # type: ignore[union-attr]
            assert "Tool calling" in text

    @pytest.mark.asyncio
    async def test_search_code_entities(
        self, mcp_configured
    ) -> None:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "search_code_entities",
                {"query": "McpHandler"},
            )
            text = result.content[0].text  # type: ignore[union-attr]
            assert "McpHandler" in text

    @pytest.mark.asyncio
    async def test_get_specification_missing(
        self, mcp_configured
    ) -> None:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_specification",
                {"section": "nonexistent"},
            )
            text = result.content[0].text  # type: ignore[union-attr]
            assert "not yet generated" in text


class TestMcpResources:
    @pytest.mark.asyncio
    async def test_list_resources(
        self, mcp_configured
    ) -> None:
        async with Client(mcp) as client:
            resources = await client.list_resources()
            assert len(resources) >= 1

    @pytest.mark.asyncio
    async def test_list_resource_templates(
        self, mcp_configured
    ) -> None:
        async with Client(mcp) as client:
            templates = (
                await client.list_resource_templates()
            )
            uris = [
                str(t.uriTemplate) for t in templates
            ]
            assert any(
                "overview" in u for u in uris
            )


class TestMcpPrompts:
    @pytest.mark.asyncio
    async def test_list_prompts(
        self, mcp_configured
    ) -> None:
        async with Client(mcp) as client:
            prompts = await client.list_prompts()
            prompt_names = {p.name for p in prompts}
            expected = {
                "explain_repo",
                "review_code",
                "write_tests",
                "fix_bug",
                "migration_plan",
            }
            assert expected == prompt_names

    @pytest.mark.asyncio
    async def test_explain_repo_prompt(
        self, mcp_configured
    ) -> None:
        async with Client(mcp) as client:
            result = await client.get_prompt(
                "explain_repo",
                {"project_id": PROJECT_ID},
            )
            text = result.messages[0].content.text  # type: ignore[union-attr]
            assert "Project Briefing" in text
            assert "MCP test project" in text
