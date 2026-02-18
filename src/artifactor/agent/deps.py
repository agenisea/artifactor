"""Agent dependency injection dataclass."""

from __future__ import annotations

from dataclasses import dataclass

from artifactor.logger import AgentLogger
from artifactor.repositories.protocols import (
    ConversationRepository,
    DocumentRepository,
    EntityRepository,
    ProjectRepository,
    RelationshipRepository,
)


@dataclass
class AgentDeps:
    """Carries all dependencies that tools need at runtime.

    Passed to every pydantic-ai agent call and accessed via
    ``ctx.deps`` in tool functions.
    """

    project_repo: ProjectRepository
    document_repo: DocumentRepository
    entity_repo: EntityRepository
    relationship_repo: RelationshipRepository
    conversation_repo: ConversationRepository
    logger: AgentLogger
    request_id: str
    project_id: str
