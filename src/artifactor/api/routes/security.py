"""Security findings route."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["security"]
)


@router.get("/security")
async def get_security(
    project_id: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """Get security findings for a project.

    Combines security_requirements and security_considerations.
    """
    reqs = await repos.document.get_section(
        project_id, "security_requirements"
    )
    considerations = await repos.document.get_section(
        project_id, "security_considerations"
    )

    data: dict[str, object] = {"project_id": project_id}
    if reqs:
        data["requirements"] = {
            "content": reqs.content,
            "confidence": reqs.confidence,
        }
    if considerations:
        data["considerations"] = {
            "content": considerations.content,
            "confidence": considerations.confidence,
        }

    return APIResponse(success=True, data=data)
