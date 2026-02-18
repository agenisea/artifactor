"""Section 11 — Integration Points generator."""

from __future__ import annotations

from artifactor.config import SECTION_TITLES, Settings
from artifactor.constants import RelationshipType
from artifactor.intelligence.model import IntelligenceModel
from artifactor.outputs.base import (
    SectionOutput,
    avg_confidence,
    generate_with_fallback,
    heading,
    table,
)

SECTION_NAME = "integrations"


async def generate(
    model: IntelligenceModel,
    project_id: str,
    settings: Settings,
) -> SectionOutput:
    """LLM-powered generation with template fallback."""
    return await generate_with_fallback(
        SECTION_NAME, model, project_id, settings,
        generate_template,
    )


def generate_template(
    model: IntelligenceModel,
    project_id: str,
) -> SectionOutput:
    """Template fallback (original implementation)."""
    kg = model.knowledge_graph

    parts: list[str] = [heading("Integration Points")]
    confidences: list[float] = []

    import_rels = [
        r for r in kg.relationships
        if r.relationship_type == RelationshipType.IMPORTS
    ]

    imports_by_target: dict[str, list[str]] = {}
    for rel in import_rels:
        imports_by_target.setdefault(
            rel.target_id, []
        ).append(rel.source_id)

    if imports_by_target:
        parts.append(heading("External Dependencies", 2))
        rows = [
            [
                f"`{target}`",
                str(len(sources)),
                ", ".join(f"`{s}`" for s in sources[:3])
                + ("..." if len(sources) > 3 else ""),
            ]
            for target, sources in sorted(
                imports_by_target.items(),
                key=lambda x: -len(x[1]),
            )
        ]
        parts.append(
            table(["Module", "Importers", "Used By"], rows)
        )

    if not import_rels:
        parts.append("No integration points discovered.\n")

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )
