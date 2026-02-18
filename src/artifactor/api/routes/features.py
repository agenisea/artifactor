"""Feature listing route."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["features"]
)


@router.get("/features")
async def get_features(
    project_id: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """Get features extracted from project analysis."""
    doc = await repos.document.get_section(
        project_id, "features"
    )

    if doc is None:
        return APIResponse(
            success=True,
            data={"project_id": project_id, "features": []},
        )

    return APIResponse(
        success=True,
        data={
            "project_id": project_id,
            "content": doc.content,
            "confidence": doc.confidence,
        },
    )
