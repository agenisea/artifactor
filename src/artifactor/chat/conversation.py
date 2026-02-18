"""Conversation lifecycle: create, get history, add messages."""

from __future__ import annotations

import json

from artifactor.intelligence.value_objects import Citation
from artifactor.models.conversation import (
    Conversation,
    Message,
)
from artifactor.repositories.protocols import (
    ConversationRepository,
)


async def create_conversation(
    project_id: str,
    title: str | None,
    repo: ConversationRepository,
) -> Conversation:
    """Create a new conversation for a project."""
    conv = Conversation(
        project_id=project_id,
        title=title,
    )
    return await repo.create_conversation(conv)


async def get_conversation(
    conversation_id: str,
    repo: ConversationRepository,
) -> Conversation | None:
    """Get a conversation by ID."""
    return await repo.get_conversation(conversation_id)


async def get_history(
    conversation_id: str,
    repo: ConversationRepository,
) -> list[Message]:
    """Get all messages in a conversation, ordered by time."""
    return await repo.get_messages(conversation_id)


async def add_user_message(
    conversation_id: str,
    content: str,
    repo: ConversationRepository,
) -> Message:
    """Add a user message to a conversation."""
    msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=content,
    )
    return await repo.add_message(msg)


async def add_assistant_message(
    conversation_id: str,
    content: str,
    citations: list[Citation] | None = None,
    repo: ConversationRepository | None = None,
) -> Message:
    """Add an assistant message with optional citations."""
    if repo is None:
        msg = "ConversationRepository is required"
        raise ValueError(msg)

    citations_json: str | None = None
    if citations:
        citations_json = json.dumps(
            [
                {
                    "file_path": c.file_path,
                    "function_name": c.function_name,
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                    "confidence": c.confidence,
                }
                for c in citations
            ]
        )

    msg_obj = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        citations_json=citations_json,
    )
    return await repo.add_message(msg_obj)


def parse_citations_json(
    citations_json: str | None,
) -> list[Citation]:
    """Parse stored citations_json back to Citation objects."""
    if not citations_json:
        return []
    data = json.loads(citations_json)
    return [
        Citation(
            file_path=item["file_path"],
            function_name=item.get("function_name"),
            line_start=item["line_start"],
            line_end=item["line_end"],
            confidence=item.get("confidence", 0.0),
        )
        for item in data
    ]
