"""MCP resource definitions: 5 resources for project data."""

# pyright: reportUnusedFunction=false
# All functions are registered via @mcp.resource decorator

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from artifactor.repositories.document_repo import (
    SqlDocumentRepository,
)
from artifactor.repositories.project_repo import (
    SqlProjectRepository,
)


def register_resources(mcp: FastMCP) -> None:
    """Register all 5 MCP resources."""

    @mcp.resource("artifactor://projects")
    async def list_projects() -> str:
        """List all analyzed projects with status."""
        async with _session_project_repo() as repo:
            projects = await repo.list_all()
        if not projects:
            return "No projects found."
        items: list[dict[str, str]] = []
        for p in projects:
            items.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "status": p.status,
                }
            )
        return json.dumps(items, indent=2)

    @mcp.resource(
        "artifactor://project/{project_id}/overview"
    )
    async def project_overview(
        project_id: str,
    ) -> str:
        """Executive summary for a project."""
        async with _session_document_repo() as doc_repo:
            doc = await doc_repo.get_section(
                project_id, "executive_overview"
            )
        if doc is None:
            return (
                "Executive overview not yet generated."
            )
        return doc.content

    @mcp.resource(
        "artifactor://project/{project_id}/sections"
    )
    async def project_sections(
        project_id: str,
    ) -> str:
        """Available documentation sections."""
        async with _session_document_repo() as doc_repo:
            docs = await doc_repo.list_sections(project_id)
        if not docs:
            return "No sections generated yet."
        items = [
            {
                "section_name": d.section_name,
                "confidence": d.confidence,
            }
            for d in docs
        ]
        return json.dumps(items, indent=2)

    @mcp.resource(
        "artifactor://project/{project_id}"
        "/section/{section_name}"
    )
    async def section_content(
        project_id: str,
        section_name: str,
    ) -> str:
        """Full section content as markdown."""
        async with _session_document_repo() as doc_repo:
            doc = await doc_repo.get_section(
                project_id, section_name
            )
        if doc is None:
            return (
                f"Section '{section_name}' not found."
            )
        return doc.content

    @mcp.resource(
        "artifactor://project/{project_id}"
        "/diagram/{diagram_type}"
    )
    async def diagram_source(
        project_id: str,
        diagram_type: str,
    ) -> str:
        """Mermaid diagram source for a diagram type."""
        valid_types = {
            "architecture",
            "er",
            "call_graph",
            "component",
            "sequence",
        }
        if diagram_type not in valid_types:
            return (
                f"Invalid diagram type "
                f"'{diagram_type}'. "
                f"Valid: {', '.join(sorted(valid_types))}"
            )
        return (
            f"graph TD\n"
            f"    A[{diagram_type} diagram] "
            f"--> B[Not yet generated for "
            f"{project_id}]"
        )


@asynccontextmanager
async def _session_project_repo() -> (
    AsyncIterator[SqlProjectRepository]
):
    """Yield project repo with proper session lifecycle."""
    from artifactor.mcp.server import (
        get_session_factory,
    )

    factory = get_session_factory()
    async with factory() as session:
        yield SqlProjectRepository(session)


@asynccontextmanager
async def _session_document_repo() -> (
    AsyncIterator[SqlDocumentRepository]
):
    """Yield document repo with proper session lifecycle."""
    from artifactor.mcp.server import (
        get_session_factory,
    )

    factory = get_session_factory()
    async with factory() as session:
        yield SqlDocumentRepository(session)
