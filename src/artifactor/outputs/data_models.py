"""Section 7 — Data Models generator."""

from __future__ import annotations

from artifactor.config import SECTION_TITLES, Settings
from artifactor.intelligence.knowledge_graph import (
    GraphEntity,
    KnowledgeGraph,
)
from artifactor.intelligence.model import IntelligenceModel
from artifactor.outputs.base import (
    SectionOutput,
    avg_confidence,
    fenced_code,
    generate_with_fallback,
    heading,
    table,
)

SECTION_NAME = "data_models"


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

    parts: list[str] = [heading("Data Models")]
    confidences: list[float] = []

    classes = kg.find_by_type("class")
    tables = kg.find_by_type("table")
    table_sources = {(e.file_path, e.name) for e in tables}
    unique_classes = [
        c for c in classes
        if (c.file_path, c.name) not in table_sources
    ]
    data_entities = unique_classes + tables

    if data_entities:
        parts.append(heading("Entities", 2))
        rows = [
            [f"`{e.name}`", e.entity_type,
             f"`{e.file_path}:{e.start_line}`",
             e.description or "—"]
            for e in sorted(data_entities, key=lambda x: x.name)
        ]
        parts.append(
            table(
                ["Name", "Type", "Location", "Description"],
                rows,
            )
        )
        confidences.extend(
            e.confidence.value for e in data_entities
        )

    if len(data_entities) >= 2:
        parts.append(heading("Entity-Relationship Diagram", 2))
        mermaid = _generate_er_mermaid(data_entities, kg)
        parts.append(fenced_code(mermaid, "mermaid"))

    data_ids = {e.id for e in data_entities}
    data_rels = [
        r for r in kg.relationships
        if r.source_id in data_ids or r.target_id in data_ids
    ]
    if data_rels:
        parts.append(heading("Relationships", 2))
        rel_rows = [
            [f"`{r.source_id}`", r.relationship_type,
             f"`{r.target_id}`"]
            for r in data_rels
        ]
        parts.append(
            table(["Source", "Relationship", "Target"], rel_rows)
        )

    if not data_entities:
        parts.append(
            "No data model entities (class, table) "
            "discovered in the codebase.\n"
        )

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )


def _generate_er_mermaid(
    entities: list[GraphEntity], kg: KnowledgeGraph,
) -> str:
    """Generate a Mermaid ER diagram."""
    lines = ["erDiagram"]
    entity_ids = {e.id for e in entities}
    for e in entities:
        safe_name = e.name.replace(" ", "_")
        lines.append(f"    {safe_name} {{")
        lines.append("        string id")
        lines.append("    }")

    for rel in kg.relationships:
        if (
            rel.source_id in entity_ids
            and rel.target_id in entity_ids
        ):
            src = _get_name(rel.source_id, entities)
            tgt = _get_name(rel.target_id, entities)
            lines.append(
                f"    {src} ||--o{{ {tgt} : "
                f'"{rel.relationship_type}"'
            )

    return "\n".join(lines)


def _get_name(
    entity_id: str, entities: list[GraphEntity],
) -> str:
    """Get display name from entity ID."""
    for e in entities:
        if e.id == entity_id:
            return e.name.replace(" ", "_")
    return (
        entity_id.split("::")[-1]
        if "::" in entity_id
        else entity_id
    )
