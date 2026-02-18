"""Protocol-based repository interfaces.

SQL implementations satisfy these protocols structurally (no inheritance).
Test doubles can be plain classes or mocks matching the same signature.
"""

from typing import Protocol

from artifactor.models.checkpoint import AnalysisCheckpoint
from artifactor.models.conversation import Conversation, Message
from artifactor.models.document import Document
from artifactor.models.entity import CodeEntityRecord
from artifactor.models.project import Project
from artifactor.models.relationship import Relationship


class ProjectRepository(Protocol):
    async def get_by_id(self, project_id: str) -> Project | None: ...
    async def list_all(self) -> list[Project]: ...
    async def create(self, project: Project) -> Project: ...
    async def update_status(self, project_id: str, status: str) -> None: ...
    async def try_set_status(
        self, project_id: str, expected: set[str], new_status: str
    ) -> bool: ...
    async def delete(self, project_id: str) -> None: ...


class DocumentRepository(Protocol):
    async def get_section(
        self, project_id: str, section_name: str
    ) -> Document | None: ...
    async def list_sections(self, project_id: str) -> list[Document]: ...
    async def upsert_section(self, document: Document) -> Document: ...
    async def delete_sections(self, project_id: str) -> None: ...


class EntityRepository(Protocol):
    async def search(
        self,
        project_id: str,
        query: str,
        entity_type: str | None = None,
    ) -> list[CodeEntityRecord]: ...
    async def get_by_path(
        self, project_id: str, file_path: str
    ) -> list[CodeEntityRecord]: ...
    async def bulk_insert(self, entities: list[CodeEntityRecord]) -> None: ...
    async def delete_by_project(self, project_id: str) -> None: ...


class RelationshipRepository(Protocol):
    async def get_callers(
        self,
        project_id: str,
        file_path: str,
        symbol_name: str,
        depth: int = 1,
    ) -> list[Relationship]: ...
    async def get_callees(
        self,
        project_id: str,
        file_path: str,
        symbol_name: str,
        depth: int = 1,
    ) -> list[Relationship]: ...
    async def list_by_project(
        self, project_id: str
    ) -> list[Relationship]: ...
    async def bulk_insert(self, relationships: list[Relationship]) -> None: ...
    async def delete_by_project(self, project_id: str) -> None: ...


class ConversationRepository(Protocol):
    async def get_conversations(
        self, project_id: str
    ) -> list[Conversation]: ...
    async def get_conversation(
        self, conversation_id: str
    ) -> Conversation | None: ...
    async def create_conversation(
        self, conversation: Conversation
    ) -> Conversation: ...
    async def get_messages(
        self, conversation_id: str
    ) -> list[Message]: ...
    async def add_message(self, message: Message) -> Message: ...


class CheckpointRepository(Protocol):
    async def get(
        self, project_id: str, chunk_hash: str
    ) -> AnalysisCheckpoint | None: ...
    async def put(self, checkpoint: AnalysisCheckpoint) -> None: ...
    async def count(self, project_id: str) -> int: ...
    async def invalidate(self, project_id: str) -> int: ...
