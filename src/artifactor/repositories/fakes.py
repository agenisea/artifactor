"""In-memory fake repositories for testing.

Dict-backed implementations of all 5 repository protocols.
No SQLAlchemy, no I/O — instant operations for unit tests.
"""

# pyright: reportUnusedFunction=false

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from artifactor.constants import ID_HEX_LENGTH, ProjectStatus
from artifactor.models.conversation import Conversation, Message
from artifactor.models.document import Document
from artifactor.models.entity import CodeEntityRecord
from artifactor.models.project import Project
from artifactor.models.relationship import Relationship


class FakeProjectRepository:
    """Dict-backed ProjectRepository for testing."""

    def __init__(self) -> None:
        self._store: dict[str, Project] = {}

    async def get_by_id(self, project_id: str) -> Project | None:
        return self._store.get(project_id)

    async def list_all(self) -> list[Project]:
        return list(self._store.values())

    async def create(self, project: Project) -> Project:
        if not project.id:
            project.id = uuid.uuid4().hex[:ID_HEX_LENGTH]
        now = datetime.now(UTC)
        project.created_at = now
        project.updated_at = now
        self._store[project.id] = project
        return project

    async def update_status(
        self, project_id: str, status: str
    ) -> None:
        proj = self._store.get(project_id)
        if proj:
            proj.status = status

    async def try_set_status(
        self, project_id: str, expected: set[str], new_status: str
    ) -> bool:
        """CAS: set status only if current status is in expected set."""
        proj = self._store.get(project_id)
        if proj and proj.status in expected:
            proj.status = new_status
            return True
        return False

    async def delete(self, project_id: str) -> None:
        self._store.pop(project_id, None)


class FakeDocumentRepository:
    """Dict-backed DocumentRepository for testing."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], Document] = {}

    async def get_section(
        self, project_id: str, section_name: str
    ) -> Document | None:
        return self._store.get((project_id, section_name))

    async def list_sections(
        self, project_id: str
    ) -> list[Document]:
        return [
            doc
            for (pid, _), doc in self._store.items()
            if pid == project_id
        ]

    async def upsert_section(
        self, document: Document
    ) -> Document:
        if not document.id:
            document.id = uuid.uuid4().hex[:ID_HEX_LENGTH]
        key = (document.project_id, document.section_name)
        self._store[key] = document
        return document

    async def delete_sections(
        self, project_id: str
    ) -> None:
        keys = [
            k for k in self._store if k[0] == project_id
        ]
        for k in keys:
            del self._store[k]


class FakeEntityRepository:
    """List-backed EntityRepository for testing."""

    def __init__(self) -> None:
        self._store: list[CodeEntityRecord] = []

    async def search(
        self,
        project_id: str,
        query: str,
        entity_type: str | None = None,
    ) -> list[CodeEntityRecord]:
        results = [
            e
            for e in self._store
            if e.project_id == project_id
        ]
        if query:
            q = query.lower()
            results = [
                e
                for e in results
                if q in e.name.lower()
                or q in e.file_path.lower()
            ]
        if entity_type:
            results = [
                e
                for e in results
                if e.entity_type == entity_type
            ]
        return results

    async def get_by_path(
        self, project_id: str, file_path: str
    ) -> list[CodeEntityRecord]:
        return [
            e
            for e in self._store
            if e.project_id == project_id
            and e.file_path == file_path
        ]

    async def bulk_insert(
        self, entities: list[CodeEntityRecord]
    ) -> None:
        for entity in entities:
            if not entity.id:
                entity.id = uuid.uuid4().hex[:ID_HEX_LENGTH]
        self._store.extend(entities)

    async def delete_by_project(
        self, project_id: str
    ) -> None:
        self._store = [
            e for e in self._store
            if e.project_id != project_id
        ]


class FakeRelationshipRepository:
    """List-backed RelationshipRepository for testing."""

    def __init__(self) -> None:
        self._store: list[Relationship] = []

    async def get_callers(
        self,
        project_id: str,
        file_path: str,
        symbol_name: str,
        depth: int = 1,
    ) -> list[Relationship]:
        return [
            r
            for r in self._store
            if r.project_id == project_id
            and r.target_file == file_path
            and r.target_symbol == symbol_name
        ]

    async def get_callees(
        self,
        project_id: str,
        file_path: str,
        symbol_name: str,
        depth: int = 1,
    ) -> list[Relationship]:
        return [
            r
            for r in self._store
            if r.project_id == project_id
            and r.source_file == file_path
            and r.source_symbol == symbol_name
        ]

    async def list_by_project(
        self, project_id: str
    ) -> list[Relationship]:
        return [
            r
            for r in self._store
            if r.project_id == project_id
        ]

    async def bulk_insert(
        self, relationships: list[Relationship]
    ) -> None:
        self._store.extend(relationships)

    async def delete_by_project(
        self, project_id: str
    ) -> None:
        self._store = [
            r for r in self._store
            if r.project_id != project_id
        ]


class FakeConversationRepository:
    """Dict+list-backed ConversationRepository for testing."""

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._messages: list[Message] = []

    async def get_conversations(
        self, project_id: str
    ) -> list[Conversation]:
        return [
            c
            for c in self._conversations.values()
            if c.project_id == project_id
        ]

    async def get_conversation(
        self, conversation_id: str
    ) -> Conversation | None:
        return self._conversations.get(conversation_id)

    async def create_conversation(
        self, conversation: Conversation
    ) -> Conversation:
        if not conversation.id:
            conversation.id = uuid.uuid4().hex[:ID_HEX_LENGTH]
        conversation.created_at = datetime.now(UTC)
        self._conversations[conversation.id] = conversation
        return conversation

    async def get_messages(
        self, conversation_id: str
    ) -> list[Message]:
        return [
            m
            for m in self._messages
            if m.conversation_id == conversation_id
        ]

    async def add_message(self, message: Message) -> Message:
        if not message.id:
            message.id = uuid.uuid4().hex[:ID_HEX_LENGTH]
        message.created_at = datetime.now(UTC)
        self._messages.append(message)
        return message


# ── Service fakes ─────────────────────────────────────


class FakeProjectService:
    """Test double for ProjectService backed by FakeProjectRepository."""

    def __init__(
        self, repo: FakeProjectRepository
    ) -> None:
        self._repo = repo

    async def list_all(self) -> list[Project]:
        return await self._repo.list_all()

    async def get(self, project_id: str) -> Project | None:
        return await self._repo.get_by_id(project_id)

    async def create(
        self,
        name: str,
        local_path: str | None = None,
        branch: str | None = None,
    ) -> Project:
        project = Project(
            name=name,
            local_path=local_path,
            branch=branch,
            status=ProjectStatus.PENDING,
        )
        return await self._repo.create(project)

    async def delete(self, project_id: str) -> None:
        await self._repo.delete(project_id)

    async def update_status(
        self, project_id: str, status: str
    ) -> None:
        await self._repo.update_status(project_id, status)

    async def try_set_status(
        self, project_id: str, expected: set[str], new_status: str
    ) -> bool:
        return await self._repo.try_set_status(
            project_id, expected, new_status
        )

    async def update_status_immediate(
        self, project_id: str, status: str
    ) -> None:
        await self._repo.update_status(project_id, status)

    async def try_set_status_immediate(
        self, project_id: str, expected: set[str], new_status: str
    ) -> bool:
        return await self._repo.try_set_status(
            project_id, expected, new_status
        )


class FakeDataService:
    """Test double for DataService — always healthy."""

    async def check_connection(self) -> bool:
        return True

    async def check_vector_store(self) -> bool:
        return True

    def check_mermaid_cli(self) -> bool:
        return False
