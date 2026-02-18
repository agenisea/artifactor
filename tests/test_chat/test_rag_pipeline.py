"""Tests for the RAG pipeline."""

from __future__ import annotations

import pytest

from artifactor.chat.rag_pipeline import (
    RetrievedContext,
    _extract_keywords,
    _format_context,
    retrieve_context,
)
from artifactor.models.document import Document
from artifactor.models.entity import CodeEntityRecord
from artifactor.repositories.fakes import (
    FakeDocumentRepository,
    FakeEntityRepository,
)

PROJECT_ID = "test-proj-rag"


@pytest.fixture
async def repos():
    """Create repos with seeded data for RAG tests."""
    entity_repo = FakeEntityRepository()
    document_repo = FakeDocumentRepository()

    # Seed entities
    entities = [
        CodeEntityRecord(
            project_id=PROJECT_ID,
            name="UserService",
            entity_type="class",
            file_path="src/services/user.py",
            start_line=10,
            end_line=50,
            language="python",
        ),
        CodeEntityRecord(
            project_id=PROJECT_ID,
            name="login_handler",
            entity_type="function",
            file_path="src/routes/auth.py",
            start_line=5,
            end_line=20,
            language="python",
        ),
        CodeEntityRecord(
            project_id=PROJECT_ID,
            name="DatabaseConfig",
            entity_type="class",
            file_path="src/config.py",
            start_line=1,
            end_line=15,
            language="python",
        ),
    ]
    await entity_repo.bulk_insert(entities)

    # Seed documents
    docs = [
        Document(
            project_id=PROJECT_ID,
            section_name="features",
            content=(
                "## Features\n"
                "- User authentication via login_handler\n"
                "- Database management\n"
            ),
            confidence=0.9,
        ),
        Document(
            project_id=PROJECT_ID,
            section_name="executive_overview",
            content=(
                "## Overview\n"
                "A web application with user management.\n"
            ),
            confidence=0.85,
        ),
        Document(
            project_id=PROJECT_ID,
            section_name="api_specs",
            content=(
                "## API Specs\n"
                "POST /login - authenticate user\n"
            ),
            confidence=0.8,
        ),
    ]
    for doc in docs:
        await document_repo.upsert_section(doc)

    return entity_repo, document_repo


class TestExtractKeywords:
    def test_filters_stop_words(self) -> None:
        keywords = _extract_keywords(
            "what is the login handler for authentication"
        )
        assert "login" in keywords
        assert "handler" in keywords
        assert "authentication" in keywords
        assert "what" not in keywords
        assert "is" not in keywords
        assert "the" not in keywords

    def test_filters_short_words(self) -> None:
        keywords = _extract_keywords("a is to me go")
        # "me" and "go" are 2 chars, filtered out
        assert keywords == []

    def test_empty_query(self) -> None:
        assert _extract_keywords("") == []
        assert _extract_keywords("   ") == []


class TestFormatContext:
    def test_empty_context(self) -> None:
        result = _format_context([], [])
        assert result == "No context found."

    def test_with_entities_only(self) -> None:
        entity = CodeEntityRecord(
            project_id="p1",
            name="MyClass",
            entity_type="class",
            file_path="main.py",
            start_line=1,
            end_line=10,
            language="python",
        )
        result = _format_context([entity], [])
        assert "MyClass" in result
        assert "main.py" in result
        assert "## Code Entities" in result

    def test_with_documents_only(self) -> None:
        doc = Document(
            project_id="p1",
            section_name="features",
            content="Feature list here.",
            confidence=0.9,
        )
        result = _format_context([], [doc])
        assert "features" in result
        assert "Feature list here." in result

    def test_with_both(self) -> None:
        entity = CodeEntityRecord(
            project_id="p1",
            name="Foo",
            entity_type="function",
            file_path="foo.py",
            start_line=5,
            end_line=15,
            language="python",
        )
        doc = Document(
            project_id="p1",
            section_name="overview",
            content="Project overview.",
            confidence=0.9,
        )
        result = _format_context([entity], [doc])
        assert "## Code Entities" in result
        assert "## Documentation Sections" in result
        assert "Foo" in result
        assert "Project overview." in result


class TestRetrievedContext:
    def test_defaults(self) -> None:
        ctx = RetrievedContext()
        assert ctx.entities == []
        assert ctx.documents == []
        assert ctx.formatted == ""

    def test_frozen(self) -> None:
        ctx = RetrievedContext(formatted="test")
        with pytest.raises(AttributeError):
            ctx.formatted = "changed"  # type: ignore[misc]


class TestRetrieveContext:
    @pytest.mark.asyncio
    async def test_search_by_keyword(self, repos) -> None:
        entity_repo, document_repo = repos
        ctx = await retrieve_context(
            "UserService class",
            PROJECT_ID,
            entity_repo,
            document_repo,
        )
        assert len(ctx.entities) >= 1
        names = [e.name for e in ctx.entities]
        assert "UserService" in names
        assert ctx.formatted != "No context found."

    @pytest.mark.asyncio
    async def test_search_finds_documents(
        self, repos
    ) -> None:
        entity_repo, document_repo = repos
        ctx = await retrieve_context(
            "login authentication",
            PROJECT_ID,
            entity_repo,
            document_repo,
        )
        # Should find the features doc (mentions login_handler)
        assert len(ctx.documents) >= 1
        section_names = [
            d.section_name for d in ctx.documents
        ]
        assert "features" in section_names

    @pytest.mark.asyncio
    async def test_no_results(self, repos) -> None:
        entity_repo, document_repo = repos
        ctx = await retrieve_context(
            "xyznonexistent",
            PROJECT_ID,
            entity_repo,
            document_repo,
        )
        assert ctx.entities == []
        assert ctx.formatted == "No context found."

    @pytest.mark.asyncio
    async def test_max_entities_limit(
        self, repos
    ) -> None:
        entity_repo, document_repo = repos
        ctx = await retrieve_context(
            "src",
            PROJECT_ID,
            entity_repo,
            document_repo,
            max_entities=1,
        )
        assert len(ctx.entities) <= 1


class TestVectorResultCoercion:
    @pytest.mark.asyncio
    async def test_corrupted_row_skipped(self) -> None:
        """Rows with non-coercible types are skipped, not crash."""
        from unittest.mock import AsyncMock, patch

        from artifactor.chat.rag_pipeline import _search_vectors
        from artifactor.config import Settings

        corrupted_rows = [
            {
                "file_path": "good.py",
                "symbol_name": "func",
                "content": "code",
                "start_line": "not_a_number",
                "end_line": 10,
                "_distance": 0.5,
            },
            {
                "file_path": "ok.py",
                "symbol_name": "func2",
                "content": "code2",
                "start_line": 1,
                "end_line": 5,
                "_distance": 0.3,
            },
        ]

        settings = Settings(database_url="sqlite:///:memory:")

        with patch(
            "artifactor.chat.rag_pipeline.embed_text",
            new_callable=AsyncMock,
            return_value=[0.1, 0.2],
        ), patch(
            "artifactor.chat.rag_pipeline._guarded_vector_query",
            new_callable=AsyncMock,
            return_value=corrupted_rows,
        ):
            results = await _search_vectors("test", settings)

        # First row skipped (bad start_line), second row kept
        assert len(results) == 1
        assert results[0].file_path == "ok.py"
