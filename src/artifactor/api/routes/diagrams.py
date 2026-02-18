"""Diagram generation route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse
from artifactor.diagrams.mermaid import (
    generate_architecture_diagram,
    generate_call_graph_diagram,
    generate_er_diagram,
    generate_sequence_diagram_from_calls,
)
from artifactor.intelligence.knowledge_graph import (
    GraphEntity,
    GraphRelationship,
    KnowledgeGraph,
)

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["diagrams"]
)

VALID_TYPES = (
    "architecture",
    "er",
    "call_graph",
    "sequence",
)

_GENERATORS = {
    "architecture": generate_architecture_diagram,
    "er": generate_er_diagram,
    "call_graph": generate_call_graph_diagram,
    "sequence": generate_sequence_diagram_from_calls,
}


@router.get("/diagrams/{diagram_type}")
async def get_diagram(
    project_id: str,
    diagram_type: str,
    repos: Repos = Depends(get_repos),
    output_format: str = Query(
        default="mermaid",
        alias="format",
        pattern="^(mermaid|svg|png)$",
    ),
) -> APIResponse:
    """Get a diagram for the project.

    Supported types: architecture, er, call_graph, sequence.
    SVG/PNG rendering requires mmdc CLI.
    """
    if diagram_type not in VALID_TYPES:
        return APIResponse(
            success=False,
            error=(
                f"Unknown diagram type '{diagram_type}'. "
                f"Valid: {', '.join(VALID_TYPES)}"
            ),
        )

    # Build KnowledgeGraph from stored entities + relationships
    kg = KnowledgeGraph()

    entities = await repos.entity.search(project_id, "")
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

    relationships = await repos.relationship.list_by_project(
        project_id
    )
    for r in relationships:
        kg.add_relationship(
            GraphRelationship(
                id=(
                    f"{r.source_symbol}"
                    f"->{r.target_symbol}"
                ),
                source_id=(
                    f"{r.source_file}"
                    f"::{r.source_symbol}"
                ),
                target_id=(
                    f"{r.target_file}"
                    f"::{r.target_symbol}"
                ),
                relationship_type=r.relationship_type,
            )
        )

    gen = _GENERATORS.get(diagram_type)
    if gen is None:
        return APIResponse(
            success=False,
            error=(
                f"Generator not implemented for "
                f"'{diagram_type}'"
            ),
        )

    mermaid_source = gen(kg)

    # SVG/PNG rendering via mmdc if requested
    if output_format != "mermaid":
        from artifactor.diagrams.renderer import (
            render_mermaid,
        )

        rendered = await render_mermaid(
            mermaid_source, output_format  # type: ignore[arg-type]
        )
        if isinstance(rendered, bytes):
            import base64

            encoded = base64.b64encode(rendered).decode(
                "ascii"
            )
            return APIResponse(
                success=True,
                data={
                    "project_id": project_id,
                    "diagram_type": diagram_type,
                    "format": output_format,
                    "content_base64": encoded,
                },
            )
        return APIResponse(
            success=True,
            data={
                "project_id": project_id,
                "diagram_type": diagram_type,
                "format": output_format,
                "source": rendered,
            },
        )

    return APIResponse(
        success=True,
        data={
            "project_id": project_id,
            "diagram_type": diagram_type,
            "format": "mermaid",
            "source": mermaid_source,
        },
    )
