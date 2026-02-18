"""Data model routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["data_models"]
)


@router.get("/data-models")
async def list_data_models(
    project_id: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """List data model entities (classes, tables)."""
    classes = await repos.entity.search(
        project_id, "", entity_type="class"
    )
    tables = await repos.entity.search(
        project_id, "", entity_type="table"
    )
    entities = classes + tables
    return APIResponse(
        success=True,
        data=[e.to_dict() for e in entities],
    )


@router.get("/data-models/{entity_name}")
async def get_data_model(
    project_id: str,
    entity_name: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """Get a specific data model entity by name."""
    results = await repos.entity.search(
        project_id, entity_name
    )
    matches = [
        e
        for e in results
        if e.name == entity_name
        and e.entity_type in ("class", "table")
    ]
    if not matches:
        return APIResponse(
            success=False,
            error=f"Data model '{entity_name}' not found",
        )
    return APIResponse(
        success=True,
        data=matches[0].to_dict(),
    )
