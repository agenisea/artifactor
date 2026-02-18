"""User stories route."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["user_stories"]
)


@router.get("/user-stories")
async def get_user_stories(
    project_id: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """Get user stories generated from project analysis."""
    doc = await repos.document.get_section(
        project_id, "user_stories"
    )

    if doc is None:
        return APIResponse(
            success=True,
            data={
                "project_id": project_id,
                "user_stories": [],
            },
        )

    return APIResponse(
        success=True,
        data={
            "project_id": project_id,
            "content": doc.content,
            "confidence": doc.confidence,
        },
    )
