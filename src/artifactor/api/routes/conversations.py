"""Conversation history routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["conversations"]
)


@router.get("/conversations")
async def list_conversations(
    project_id: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """List conversations for a project."""
    convs = await repos.conversation.get_conversations(
        project_id
    )
    return APIResponse(
        success=True,
        data=[c.to_dict() for c in convs],
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    project_id: str,
    conversation_id: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """Get a specific conversation with messages."""
    conv = await repos.conversation.get_conversation(
        conversation_id
    )

    if conv is None:
        return APIResponse(
            success=False, error="Conversation not found"
        )

    return APIResponse(
        success=True, data=conv.to_dict()
    )
