"""SQL implementation of ConversationRepository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artifactor.models.conversation import Conversation, Message


class SqlConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_conversations(
        self, project_id: str
    ) -> list[Conversation]:
        result = await self._session.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_conversation(
        self, conversation_id: str
    ) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def create_conversation(
        self, conversation: Conversation
    ) -> Conversation:
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get_messages(
        self, conversation_id: str
    ) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())

    async def add_message(self, message: Message) -> Message:
        self._session.add(message)
        await self._session.flush()
        return message
