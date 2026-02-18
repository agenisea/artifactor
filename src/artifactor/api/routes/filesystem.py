"""Filesystem browsing for folder picker UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request

from artifactor.api.schemas import APIResponse

router = APIRouter(prefix="/api/filesystem", tags=["filesystem"])


def _resolve_browse_root(request: Request) -> Path:
    """Return the resolved browse root from settings."""
    settings = request.app.state.settings
    if settings.browse_root:
        return Path(settings.browse_root).resolve()
    return Path.home().resolve()


@router.get("/browse")
async def browse_directory(
    request: Request, path: str | None = None
) -> APIResponse:
    """List directories at the given path for folder picker UI."""
    root = _resolve_browse_root(request)
    target = Path(path).resolve() if path else root

    if not target.is_relative_to(root):
        return APIResponse(
            success=False,
            data=None,
            error="Access denied.",
        )

    if not target.is_dir():
        return APIResponse(
            success=False,
            data=None,
            error="Not a directory.",
        )

    entries: list[dict[str, str]] = []
    try:
        for child in sorted(target.iterdir()):
            if child.name.startswith("."):
                continue
            if child.is_dir():
                entries.append({"name": child.name, "type": "directory"})
    except PermissionError:
        return APIResponse(
            success=False,
            data=None,
            error="Permission denied.",
        )

    # Clamp parent to root boundary
    if target == root:
        parent = None
    elif not target.parent.is_relative_to(root):
        parent = str(root)
    else:
        parent = str(target.parent)

    return APIResponse(
        success=True,
        data={
            "current": str(target),
            "parent": parent,
            "entries": entries,
        },
    )
