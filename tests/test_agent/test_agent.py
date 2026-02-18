"""Tests for the agent layer using pydantic-ai TestModel."""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from artifactor.agent import AgentDeps, AgentResponse, create_agent
from artifactor.logger import AgentLogger
from artifactor.repositories.fakes import (
    FakeConversationRepository,
    FakeDocumentRepository,
    FakeEntityRepository,
    FakeProjectRepository,
    FakeRelationshipRepository,
)


@pytest.fixture
def deps(tmp_path):
    """Create AgentDeps with fake repos."""
    return AgentDeps(
        project_repo=FakeProjectRepository(),
        document_repo=FakeDocumentRepository(),
        entity_repo=FakeEntityRepository(),
        relationship_repo=FakeRelationshipRepository(),
        conversation_repo=FakeConversationRepository(),
        logger=AgentLogger(log_dir=tmp_path / "logs"),
        request_id="test-req-1",
        project_id="test-proj-1",
    )


class TestAgentCreation:
    def test_create_agent_with_test_model(self) -> None:
        model = TestModel()
        agent = create_agent(model=model)
        assert agent is not None

    def test_agent_has_tools_registered(self) -> None:
        model = TestModel()
        agent = create_agent(model=model)
        toolset = agent._function_toolset  # pyright: ignore[reportPrivateUsage]
        tool_names = set(toolset.tools.keys())
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

    def test_agent_output_type(self) -> None:
        model = TestModel()
        agent = create_agent(model=model)
        assert agent.output_type is AgentResponse


class TestAgentResponse:
    def test_response_defaults(self) -> None:
        resp = AgentResponse(message="Hello")
        assert resp.message == "Hello"
        assert resp.citations == []
        assert resp.confidence is None
        assert resp.tools_used == []

    def test_response_with_citations(self) -> None:
        from artifactor.agent.schemas import CitationRef

        resp = AgentResponse(
            message="Found it",
            citations=[
                CitationRef(
                    file_path="main.py",
                    line_start=1,
                    line_end=10,
                    confidence=0.9,
                )
            ],
            tools_used=["search_code_entities"],
        )
        assert len(resp.citations) == 1
        assert resp.citations[0].file_path == "main.py"
        assert resp.tools_used == ["search_code_entities"]


class TestAgentDeps:
    @pytest.mark.asyncio
    async def test_deps_have_repos(
        self, deps: AgentDeps
    ) -> None:
        assert deps.project_id == "test-proj-1"
        assert deps.request_id == "test-req-1"

    @pytest.mark.asyncio
    async def test_entity_repo_search_empty(
        self, deps: AgentDeps
    ) -> None:
        results = await deps.entity_repo.search(
            "test-proj-1", "foo"
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_document_repo_get_section_none(
        self, deps: AgentDeps
    ) -> None:
        result = await deps.document_repo.get_section(
            "test-proj-1", "features"
        )
        assert result is None


class TestSystemPrompt:
    def test_prompt_has_jtbd_sections(self) -> None:
        """SYSTEM_PROMPT must contain all JTBD framework sections."""
        from artifactor.prompts import CHAT_AGENT_PROMPT as SYSTEM_PROMPT

        for section in [
            "Job To Be Done",
            "Success Criteria",
            "Available Tools",
            "Core Axioms",
            "Boundaries",
            "Examples",
        ]:
            assert section in SYSTEM_PROMPT, (
                f"Missing section: {section}"
            )

    def test_prompt_preserves_axioms(self) -> None:
        """All 5 original axioms must still be present."""
        from artifactor.prompts import CHAT_AGENT_PROMPT as SYSTEM_PROMPT

        axiom_keywords = [
            "Understanding > Action",
            "Verified Citation > Broader Coverage",
            "Honesty > Impression",
            "Local-First > Convenience",
            "Language-Agnostic > Language-Specific",
        ]
        for kw in axiom_keywords:
            assert kw in SYSTEM_PROMPT, (
                f"Missing axiom: {kw}"
            )


class TestToolErrorHandling:
    def test_handle_tool_errors_catches_exception(
        self,
    ) -> None:
        import asyncio

        from artifactor.agent.tools import (
            handle_tool_errors,
        )

        @handle_tool_errors
        async def bad_tool() -> str:
            msg = "test error"
            raise ValueError(msg)

        result = asyncio.run(bad_tool())
        assert "Tool error (ValueError): test error" in result

    def test_handle_tool_errors_passes_success(
        self,
    ) -> None:
        import asyncio

        from artifactor.agent.tools import (
            handle_tool_errors,
        )

        @handle_tool_errors
        async def good_tool() -> str:
            return "success"

        result = asyncio.run(good_tool())
        assert result == "success"
