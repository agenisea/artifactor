"""FastAPI dependency injection for repository access."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request

from artifactor.repositories.protocols import (
    ConversationRepository,
    DocumentRepository,
    EntityRepository,
    ProjectRepository,
    RelationshipRepository,
)

if TYPE_CHECKING:
    from artifactor.services.data_service import DataService
    from artifactor.services.project_service import (
        ProjectService,
    )

logger = logging.getLogger(__name__)


@dataclass
class Repos:
    """Repository container resolved per-request via Depends.

    Bundles all 5 repository protocols into a single injectable
    unit. Routes receive this instead of touching session_factory.
    """

    project: ProjectRepository
    document: DocumentRepository
    entity: EntityRepository
    relationship: RelationshipRepository
    conversation: ConversationRepository


async def get_repos(
    request: Request,
) -> AsyncIterator[Repos]:
    """Generator dep — session lives for entire request."""
    from artifactor.repositories.conversation_repo import (
        SqlConversationRepository,
    )
    from artifactor.repositories.document_repo import (
        SqlDocumentRepository,
    )
    from artifactor.repositories.entity_repo import (
        SqlEntityRepository,
    )
    from artifactor.repositories.project_repo import (
        SqlProjectRepository,
    )
    from artifactor.repositories.relationship_repo import (
        SqlRelationshipRepository,
    )

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield Repos(
            project=SqlProjectRepository(session),
            document=SqlDocumentRepository(session),
            entity=SqlEntityRepository(session),
            relationship=SqlRelationshipRepository(session),
            conversation=SqlConversationRepository(session),
        )


async def get_project_service(
    request: Request,
) -> AsyncIterator[ProjectService]:
    """Generator dep — session lives for entire request."""
    from artifactor.repositories.project_repo import (
        SqlProjectRepository,
    )
    from artifactor.services.project_service import (
        ProjectService,
    )

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        repo = SqlProjectRepository(session)
        yield ProjectService(
            repo, session_factory=session_factory
        )
        try:
            await session.commit()
        except Exception:
            logger.debug(
                "session commit failed during cleanup"
                " (likely SSE disconnect)"
            )


def get_data_service(request: Request) -> DataService:
    """Get DataService from app.state."""
    return request.app.state.data_service  # type: ignore[no-any-return]
