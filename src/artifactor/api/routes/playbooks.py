"""Playbook gallery API routes."""

from __future__ import annotations

from fastapi import APIRouter

from artifactor.api.schemas import APIResponse
from artifactor.playbooks.loader import list_playbooks, load_playbook

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


@router.get("")
async def get_playbooks() -> APIResponse:
    """List all playbooks with summary metadata."""
    metas = list_playbooks()
    return APIResponse(
        success=True,
        data=[
            {
                "name": m.name,
                "title": m.title,
                "description": m.description,
                "agent": m.agent,
                "difficulty": m.difficulty,
                "estimated_time": m.estimated_time,
                "mcp_prompt": m.mcp_prompt,
                "tags": list(m.tags),
                "step_count": m.step_count,
                "tools_used": list(m.tools_used),
            }
            for m in metas
        ],
    )


@router.get("/{name}")
async def get_playbook(name: str) -> APIResponse:
    """Get full playbook detail including steps and example prompt."""
    try:
        pb = load_playbook(name)
    except FileNotFoundError:
        return APIResponse(
            success=False,
            error=f"Playbook '{name}' not found",
        )
    except ValueError as exc:
        return APIResponse(success=False, error=str(exc))

    return APIResponse(
        success=True,
        data={
            "name": pb.name,
            "title": pb.title,
            "description": pb.description,
            "agent": pb.agent,
            "difficulty": pb.difficulty,
            "estimated_time": pb.estimated_time,
            "mcp_prompt": pb.mcp_prompt,
            "tags": list(pb.tags),
            "step_count": pb.step_count,
            "tools_used": list(pb.tools_used),
            "steps": [
                {
                    "description": s.description,
                    "tool": s.tool,
                }
                for s in pb.steps
            ],
            "example_prompt": pb.example_prompt,
        },
    )
