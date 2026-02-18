"""Call graph route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["call_graph"]
)


@router.get("/call-graph/{file_path:path}/{symbol}")
async def get_call_graph(
    project_id: str,
    file_path: str,
    symbol: str,
    repos: Repos = Depends(get_repos),
    depth: int = Query(default=1, ge=1, le=5),
    direction: str = Query(
        default="both",
        pattern="^(callers|callees|both)$",
    ),
) -> APIResponse:
    """Get call graph for a symbol."""
    callers: list[object] = []
    callees: list[object] = []

    if direction in ("callers", "both"):
        caller_rels = await repos.relationship.get_callers(
            project_id, file_path, symbol, depth=depth
        )
        callers = [r.to_dict() for r in caller_rels]

    if direction in ("callees", "both"):
        callee_rels = await repos.relationship.get_callees(
            project_id, file_path, symbol, depth=depth
        )
        callees = [r.to_dict() for r in callee_rels]

    return APIResponse(
        success=True,
        data={
            "file_path": file_path,
            "symbol": symbol,
            "callers": callers,
            "callees": callees,
        },
    )
