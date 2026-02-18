"""Tests for conversation management and citations."""

from __future__ import annotations

import pytest

from artifactor.chat.citations import (
    filter_valid_citations,
    format_citation,
    format_citations_block,
    verify_citations,
)
from artifactor.chat.conversation import (
    add_assistant_message,
    add_user_message,
    create_conversation,
    get_conversation,
    get_history,
    parse_citations_json,
)
from artifactor.intelligence.value_objects import Citation
from artifactor.repositories.fakes import (
    FakeConversationRepository,
)

PROJECT_ID = "test-proj-conv"


@pytest.fixture
def conv_repo():
    """Create conversation repo — no seeding needed."""
    return FakeConversationRepository()


class TestConversationLifecycle:
    @pytest.mark.asyncio
    async def test_create_conversation(
        self, conv_repo
    ) -> None:
        conv = await create_conversation(
            PROJECT_ID, "Test Chat", conv_repo
        )
        assert conv.id is not None
        assert conv.project_id == PROJECT_ID
        assert conv.title == "Test Chat"

    @pytest.mark.asyncio
    async def test_create_conversation_no_title(
        self, conv_repo
    ) -> None:
        conv = await create_conversation(
            PROJECT_ID, None, conv_repo
        )
        assert conv.title is None

    @pytest.mark.asyncio
    async def test_get_conversation(
        self, conv_repo
    ) -> None:
        conv = await create_conversation(
            PROJECT_ID, "Lookup Test", conv_repo
        )
        fetched = await get_conversation(
            conv.id, conv_repo
        )
        assert fetched is not None
        assert fetched.id == conv.id
        assert fetched.title == "Lookup Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(
        self, conv_repo
    ) -> None:
        result = await get_conversation(
            "nonexistent-id", conv_repo
        )
        assert result is None


class TestMessageManagement:
    @pytest.mark.asyncio
    async def test_add_user_message(
        self, conv_repo
    ) -> None:
        conv = await create_conversation(
            PROJECT_ID, "Msg Test", conv_repo
        )
        msg = await add_user_message(
            conv.id, "Hello, what does this code do?", conv_repo
        )
        assert msg.role == "user"
        assert msg.content == "Hello, what does this code do?"
        assert msg.conversation_id == conv.id

    @pytest.mark.asyncio
    async def test_add_assistant_message_no_citations(
        self, conv_repo
    ) -> None:
        conv = await create_conversation(
            PROJECT_ID, "Assist Test", conv_repo
        )
        msg = await add_assistant_message(
            conv.id,
            "The code handles authentication.",
            repo=conv_repo,
        )
        assert msg.role == "assistant"
        assert msg.citations_json is None

    @pytest.mark.asyncio
    async def test_add_assistant_message_with_citations(
        self, conv_repo
    ) -> None:
        conv = await create_conversation(
            PROJECT_ID, "Citation Test", conv_repo
        )
        citations = [
            Citation(
                file_path="auth.py",
                function_name="login",
                line_start=10,
                line_end=25,
                confidence=0.9,
            )
        ]
        msg = await add_assistant_message(
            conv.id,
            "Found the login function.",
            citations=citations,
            repo=conv_repo,
        )
        assert msg.citations_json is not None
        parsed = parse_citations_json(msg.citations_json)
        assert len(parsed) == 1
        assert parsed[0].file_path == "auth.py"
        assert parsed[0].function_name == "login"
        assert parsed[0].line_start == 10

    @pytest.mark.asyncio
    async def test_get_history(self, conv_repo) -> None:
        conv = await create_conversation(
            PROJECT_ID, "History Test", conv_repo
        )
        await add_user_message(
            conv.id, "Question 1", conv_repo
        )
        await add_assistant_message(
            conv.id,
            "Answer 1",
            repo=conv_repo,
        )
        await add_user_message(
            conv.id, "Question 2", conv_repo
        )

        history = await get_history(conv.id, conv_repo)
        assert len(history) == 3
        assert history[0].role == "user"
        assert history[1].role == "assistant"
        assert history[2].role == "user"

    @pytest.mark.asyncio
    async def test_assistant_message_requires_repo(
        self,
    ) -> None:
        with pytest.raises(ValueError, match="required"):
            await add_assistant_message(
                "conv-1",
                "response",
                repo=None,
            )


class TestParseCitationsJson:
    def test_parse_none(self) -> None:
        assert parse_citations_json(None) == []

    def test_parse_empty_string(self) -> None:
        assert parse_citations_json("") == []

    def test_parse_valid_json(self) -> None:
        import json

        data = [
            {
                "file_path": "main.py",
                "function_name": "run",
                "line_start": 1,
                "line_end": 10,
                "confidence": 0.85,
            }
        ]
        citations = parse_citations_json(json.dumps(data))
        assert len(citations) == 1
        assert citations[0].file_path == "main.py"
        assert citations[0].confidence == 0.85


class TestCitationFormatting:
    def test_format_single_citation(self) -> None:
        c = Citation(
            file_path="main.py",
            function_name="handler",
            line_start=10,
            line_end=25,
            confidence=0.9,
        )
        result = format_citation(c)
        assert "main.py:10-25" in result
        assert "handler" in result
        assert "0.90" in result

    def test_format_single_line_citation(self) -> None:
        c = Citation(
            file_path="app.py",
            function_name=None,
            line_start=5,
            line_end=5,
            confidence=0.7,
        )
        result = format_citation(c)
        assert "app.py:5" in result
        assert "-5" not in result

    def test_format_citations_block_empty(self) -> None:
        assert format_citations_block([]) == ""

    def test_format_citations_block(self) -> None:
        citations = [
            Citation(
                file_path="a.py",
                function_name="foo",
                line_start=1,
                line_end=10,
                confidence=0.9,
            ),
            Citation(
                file_path="b.py",
                function_name=None,
                line_start=5,
                line_end=5,
                confidence=0.8,
            ),
        ]
        result = format_citations_block(citations)
        assert "**Sources:**" in result
        assert "1." in result
        assert "2." in result
        assert "a.py" in result
        assert "b.py" in result


class TestCitationVerification:
    def test_verify_valid_citation(
        self, tmp_path
    ) -> None:
        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "line1\nline2\nline3\nline4\nline5\n"
        )

        c = Citation(
            file_path="test.py",
            function_name=None,
            line_start=1,
            line_end=3,
            confidence=0.9,
        )
        results = verify_citations([c], tmp_path)
        assert len(results) == 1
        assert results[0].passed is True

    def test_verify_missing_file(
        self, tmp_path
    ) -> None:
        c = Citation(
            file_path="missing.py",
            function_name=None,
            line_start=1,
            line_end=1,
            confidence=0.5,
        )
        results = verify_citations([c], tmp_path)
        assert len(results) == 1
        assert results[0].passed is False

    def test_filter_valid_citations(
        self, tmp_path
    ) -> None:
        test_file = tmp_path / "exists.py"
        test_file.write_text("line1\nline2\nline3\n")

        citations = [
            Citation(
                file_path="exists.py",
                function_name=None,
                line_start=1,
                line_end=2,
                confidence=0.9,
            ),
            Citation(
                file_path="missing.py",
                function_name=None,
                line_start=1,
                line_end=1,
                confidence=0.5,
            ),
        ]
        valid = filter_valid_citations(
            citations, tmp_path
        )
        assert len(valid) == 1
        assert valid[0].file_path == "exists.py"
