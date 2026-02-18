"""CRUD tests for SqlConversationRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artifactor.models.conversation import (
    Conversation,
    Message,
)
from artifactor.models.project import Project
from artifactor.repositories.conversation_repo import (
    SqlConversationRepository,
)


@pytest.fixture
def repo(
    session: AsyncSession,
) -> SqlConversationRepository:
    return SqlConversationRepository(session)


@pytest.fixture
async def project_id(session: AsyncSession) -> str:
    p = Project(name="conv-test")
    session.add(p)
    await session.flush()
    return p.id


async def test_create_conversation(
    repo: SqlConversationRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    conv = Conversation(
        project_id=project_id, title="Chat 1"
    )
    created = await repo.create_conversation(conv)
    await session.commit()
    assert created.title == "Chat 1"
    assert created.id is not None


async def test_get_conversation(
    repo: SqlConversationRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    conv = Conversation(
        project_id=project_id, title="Get me"
    )
    created = await repo.create_conversation(conv)
    await session.commit()

    fetched = await repo.get_conversation(created.id)
    assert fetched is not None
    assert fetched.title == "Get me"


async def test_list_conversations(
    repo: SqlConversationRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    await repo.create_conversation(
        Conversation(
            project_id=project_id, title="A"
        )
    )
    await repo.create_conversation(
        Conversation(
            project_id=project_id, title="B"
        )
    )
    await session.commit()

    convs = await repo.get_conversations(project_id)
    assert len(convs) == 2


async def test_add_message(
    repo: SqlConversationRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    conv = Conversation(project_id=project_id)
    created = await repo.create_conversation(conv)
    await session.flush()

    msg = Message(
        conversation_id=created.id,
        role="user",
        content="Hello!",
    )
    added = await repo.add_message(msg)
    await session.commit()
    assert added.role == "user"
    assert added.content == "Hello!"


async def test_get_messages(
    repo: SqlConversationRepository,
    session: AsyncSession,
    project_id: str,
) -> None:
    conv = Conversation(project_id=project_id)
    created = await repo.create_conversation(conv)
    await session.flush()

    await repo.add_message(
        Message(
            conversation_id=created.id,
            role="user",
            content="Q",
        )
    )
    await repo.add_message(
        Message(
            conversation_id=created.id,
            role="assistant",
            content="A",
        )
    )
    await session.commit()

    msgs = await repo.get_messages(created.id)
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"


async def test_get_conversation_not_found(
    repo: SqlConversationRepository,
) -> None:
    result = await repo.get_conversation("nonexistent")
    assert result is None
