"""MCP server: FastMCP instance with configure/run helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp import FastMCP

from artifactor.mcp.prompts import register_prompts
from artifactor.mcp.resources import register_resources
from artifactor.mcp.tools import register_tools

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
    )

mcp = FastMCP(
    name="artifactor",
    version="0.1.0",
    instructions=(
        "Code intelligence platform — turns any "
        "codebase into queryable intelligence"
    ),
)

_session_factory: async_sessionmaker[AsyncSession] | None = (
    None
)
_default_project_id: str | None = None

register_tools(mcp)
register_resources(mcp)
register_prompts(mcp)


def configure(
    session_factory: async_sessionmaker[AsyncSession],
    default_project_id: str | None = None,
) -> None:
    """Set the DB session factory for MCP tools.

    Must be called before serving requests.
    """
    global _session_factory, _default_project_id  # noqa: PLW0603
    _session_factory = session_factory
    _default_project_id = default_project_id


def get_session_factory() -> (
    async_sessionmaker[AsyncSession]
):
    """Get the configured session factory."""
    if _session_factory is None:
        msg = (
            "MCP server not configured. "
            "Call configure(session_factory) first."
        )
        raise RuntimeError(msg)
    return _session_factory


def get_default_project_id() -> str | None:
    """Get the default project ID (if set)."""
    return _default_project_id
