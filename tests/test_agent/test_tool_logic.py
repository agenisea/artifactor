"""Tests for shared tool logic functions."""

from __future__ import annotations

import pytest

from artifactor.agent.tool_logic import (
    do_explain_symbol,
    do_get_api_endpoints,
    do_get_call_graph,
    do_get_data_model,
    do_get_security_findings,
    do_get_specification,
    do_get_user_stories,
    do_list_features,
    do_query_codebase,
    do_search_code_entities,
)
from artifactor.constants import (
    CALL_GRAPH_DEFAULT_DEPTH,
    CALL_GRAPH_DEFAULT_DIRECTION,
)
from artifactor.repositories.fakes import (
    FakeDocumentRepository,
    FakeEntityRepository,
    FakeRelationshipRepository,
)


@pytest.fixture
def entity_repo() -> FakeEntityRepository:
    return FakeEntityRepository()


@pytest.fixture
def document_repo() -> FakeDocumentRepository:
    return FakeDocumentRepository()


@pytest.fixture
def relationship_repo() -> FakeRelationshipRepository:
    return FakeRelationshipRepository()


class TestDoGetSpecification:
    @pytest.mark.asyncio
    async def test_missing_section(
        self, document_repo: FakeDocumentRepository
    ) -> None:
        result = await do_get_specification(
            "features", "proj-1", document_repo
        )
        assert "not yet generated" in result

    @pytest.mark.asyncio
    async def test_with_section(
        self, document_repo: FakeDocumentRepository
    ) -> None:
        from artifactor.models.document import Document

        doc = Document(
            project_id="proj-1",
            section_name="features",
            content="Feature list here",
        )
        await document_repo.upsert_section(doc)
        result = await do_get_specification(
            "features", "proj-1", document_repo
        )
        assert result == "Feature list here"


class TestDoListFeatures:
    @pytest.mark.asyncio
    async def test_no_features(
        self, document_repo: FakeDocumentRepository
    ) -> None:
        result = await do_list_features(
            "proj-1", document_repo
        )
        assert "not yet complete" in result


class TestDoGetDataModel:
    @pytest.mark.asyncio
    async def test_no_data_model(
        self,
        entity_repo: FakeEntityRepository,
        document_repo: FakeDocumentRepository,
    ) -> None:
        result = await do_get_data_model(
            "proj-1", entity_repo, document_repo
        )
        assert "not yet complete" in result

    @pytest.mark.asyncio
    async def test_entity_not_found(
        self,
        entity_repo: FakeEntityRepository,
        document_repo: FakeDocumentRepository,
    ) -> None:
        result = await do_get_data_model(
            "proj-1",
            entity_repo,
            document_repo,
            entity_name="User",
        )
        assert "not found" in result


class TestDoExplainSymbol:
    @pytest.mark.asyncio
    async def test_no_entities(
        self,
        entity_repo: FakeEntityRepository,
        relationship_repo: FakeRelationshipRepository,
    ) -> None:
        result = await do_explain_symbol(
            "main.py", "proj-1", entity_repo, relationship_repo
        )
        assert "No entities found" in result


class TestDoGetCallGraph:
    @pytest.mark.asyncio
    async def test_defaults_match_constants(self) -> None:
        """Verify do_get_call_graph defaults use named constants."""
        import inspect

        sig = inspect.signature(do_get_call_graph)
        assert (
            sig.parameters["direction"].default
            == CALL_GRAPH_DEFAULT_DIRECTION
        )
        assert (
            sig.parameters["depth"].default
            == CALL_GRAPH_DEFAULT_DEPTH
        )

    @pytest.mark.asyncio
    async def test_empty_call_graph(
        self,
        relationship_repo: FakeRelationshipRepository,
    ) -> None:
        result = await do_get_call_graph(
            "main.py",
            "process",
            "proj-1",
            relationship_repo,
        )
        # Should still return header lines even with no data
        assert "Callers of process" in result


class TestDoGetUserStories:
    @pytest.mark.asyncio
    async def test_no_stories(
        self, document_repo: FakeDocumentRepository
    ) -> None:
        result = await do_get_user_stories(
            "proj-1", document_repo
        )
        assert "not yet generated" in result


class TestDoGetApiEndpoints:
    @pytest.mark.asyncio
    async def test_no_endpoints(
        self, entity_repo: FakeEntityRepository
    ) -> None:
        result = await do_get_api_endpoints(
            "proj-1", entity_repo
        )
        assert "No API endpoints found" in result


class TestDoSearchCodeEntities:
    @pytest.mark.asyncio
    async def test_no_matches(
        self, entity_repo: FakeEntityRepository
    ) -> None:
        result = await do_search_code_entities(
            "foo", "proj-1", entity_repo
        )
        assert "No entities found" in result


class TestDoGetSecurityFindings:
    @pytest.mark.asyncio
    async def test_no_findings(
        self, document_repo: FakeDocumentRepository
    ) -> None:
        result = await do_get_security_findings(
            "proj-1", document_repo
        )
        assert "not yet complete" in result

    @pytest.mark.asyncio
    async def test_only_takes_document_repo(self) -> None:
        """Verify do_get_security_findings does NOT take entity_repo (ISP)."""
        import inspect

        sig = inspect.signature(do_get_security_findings)
        param_names = list(sig.parameters.keys())
        assert "entity_repo" not in param_names
        assert "document_repo" in param_names


class TestDoQueryCodebase:
    @pytest.mark.asyncio
    async def test_no_results(
        self,
        entity_repo: FakeEntityRepository,
        document_repo: FakeDocumentRepository,
    ) -> None:
        result = await do_query_codebase(
            "something", "proj-1", entity_repo, document_repo
        )
        assert "No" in result and (
            "relevant results" in result.lower()
            or "context" in result.lower()
        )
