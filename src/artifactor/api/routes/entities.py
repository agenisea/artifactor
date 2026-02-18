"""Code entity routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["entities"]
)


@router.get("/entities")
async def list_entities(
    project_id: str,
    repos: Repos = Depends(get_repos),
    q: str = Query(default="", description="Search query"),
    entity_type: str | None = Query(
        default=None, description="Filter by entity type"
    ),
) -> APIResponse:
    """Search code entities in a project."""
    entities = await repos.entity.search(
        project_id, q, entity_type=entity_type
    )
    return APIResponse(
        success=True,
        data=[e.to_dict() for e in entities],
    )


@router.get("/entities/{file_path:path}")
async def get_entities_by_path(
    project_id: str,
    file_path: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """Get all code entities in a specific file."""
    entities = await repos.entity.get_by_path(
        project_id, file_path
    )
    return APIResponse(
        success=True,
        data=[e.to_dict() for e in entities],
    )
