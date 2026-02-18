"""API endpoint listing route."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["api_endpoints"]
)


@router.get("/api-endpoints")
async def list_api_endpoints(
    project_id: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """List discovered API endpoints for a project."""
    endpoints = await repos.entity.search(
        project_id, "", entity_type="endpoint"
    )
    return APIResponse(
        success=True,
        data=[e.to_dict() for e in endpoints],
    )
