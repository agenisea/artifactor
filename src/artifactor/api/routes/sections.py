"""Documentation section routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse
from artifactor.config import SECTION_TITLES, Settings
from artifactor.intelligence.knowledge_graph import (
    GraphEntity,
    KnowledgeGraph,
)
from artifactor.intelligence.model import IntelligenceModel
from artifactor.intelligence.reasoning_graph import ReasoningGraph
from artifactor.models.document import Document
from artifactor.outputs import SECTION_GENERATORS

router = APIRouter(
    prefix="/api/projects/{project_id}/sections",
    tags=["sections"],
)


@router.get("")
async def list_sections(
    project_id: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """List all documentation sections for a project."""
    sections = await repos.document.list_sections(project_id)
    return APIResponse(
        success=True,
        data=[s.to_dict() for s in sections],
    )


@router.get("/{section_name}")
async def get_section(
    project_id: str,
    section_name: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """Get a specific documentation section."""
    section = await repos.document.get_section(
        project_id, section_name
    )
    if section is None:
        return APIResponse(
            success=False,
            error=f"Section '{section_name}' not found",
        )
    return APIResponse(success=True, data=section.to_dict())


@router.post("/{section_name}/regenerate")
async def regenerate_section(
    project_id: str,
    section_name: str,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """Regenerate a single documentation section.

    Rebuilds a minimal IntelligenceModel from stored entities
    and re-runs the section generator.
    """
    if section_name not in SECTION_TITLES:
        return APIResponse(
            success=False,
            error=(
                f"Unknown section '{section_name}'. "
                f"Valid: {', '.join(SECTION_TITLES)}"
            ),
        )

    gen = SECTION_GENERATORS.get(section_name)
    if gen is None:
        return APIResponse(
            success=False,
            error=f"No generator for section '{section_name}'",
        )

    entities = await repos.entity.search(project_id, "")
    if not entities:
        return APIResponse(
            success=False,
            error=(
                f"No entities found for project "
                f"'{project_id}'. Run analysis first."
            ),
        )

    # Build minimal KnowledgeGraph from stored entities
    kg = KnowledgeGraph()
    for e in entities:
        kg.add_entity(
            GraphEntity(
                id=f"{e.file_path}::{e.name}",
                name=e.name,
                entity_type=e.entity_type,
                file_path=e.file_path,
                start_line=e.start_line,
                end_line=e.end_line,
            )
        )

    model = IntelligenceModel(
        project_id=project_id,
        knowledge_graph=kg,
        reasoning_graph=ReasoningGraph(),
    )

    # Re-run the section generator
    settings = Settings()
    section = await gen(model, project_id, settings)

    # Upsert the regenerated section
    doc = Document(
        id=f"{project_id}:{section_name}",
        project_id=project_id,
        section_name=section_name,
        content=section.content,
        confidence=section.confidence,
    )
    await repos.document.upsert_section(doc)

    return APIResponse(
        success=True,
        data={
            "project_id": project_id,
            "section_name": section_name,
            "status": "regenerated",
            "confidence": section.confidence,
        },
    )


@router.get("/{section_name}/export", response_model=None)
async def export_section(
    request: Request,
    project_id: str,
    section_name: str,
    repos: Repos = Depends(get_repos),
    fmt: str = Query(
        default="markdown",
        alias="format",
        pattern="^(markdown|html|pdf|json)$",
    ),
) -> APIResponse | Response:
    """Export a section in the specified format."""
    from artifactor.export import (
        export_section as do_export,
    )
    from artifactor.outputs.base import SectionOutput

    doc = await repos.document.get_section(
        project_id, section_name
    )

    if doc is None:
        return APIResponse(
            success=False,
            error=f"Section '{section_name}' not found",
        )

    section_output = SectionOutput(
        title=SECTION_TITLES.get(
            section_name,
            section_name.replace("_", " ").title(),
        ),
        section_name=section_name,
        content=doc.content,
        confidence=doc.confidence or 0.0,
    )

    # PDF is sync + CPU-bound — run in thread to avoid
    # blocking the event loop
    if fmt == "pdf":
        pdf_bytes = await asyncio.to_thread(
            do_export, section_output, fmt
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename='
                    f'"{section_name}.pdf"'
                ),
            },
        )

    content = do_export(section_output, fmt)
    return APIResponse(
        success=True,
        data={"content": content, "format": fmt},
    )
