"""Section 6 — System Overview generator."""

from __future__ import annotations

from artifactor.config import SECTION_TITLES, Settings
from artifactor.constants import (
    SEQUENCE_DIAGRAM_MAX_CALLS,
    RelationshipType,
)
from artifactor.intelligence.knowledge_graph import KnowledgeGraph
from artifactor.intelligence.model import IntelligenceModel
from artifactor.outputs.base import (
    SectionOutput,
    avg_confidence,
    fenced_code,
    generate_with_fallback,
    heading,
)

SECTION_NAME = "system_overview"


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

    parts: list[str] = [heading("System Overview")]
    confidences: list[float] = []

    file_entities: dict[str, int] = {}
    for entity in kg.entities.values():
        file_entities[entity.file_path] = (
            file_entities.get(entity.file_path, 0) + 1
        )
        confidences.append(entity.confidence.value)

    if file_entities:
        parts.append(heading("Module Tree", 2))
        tree_lines: list[str] = []
        for fpath in sorted(file_entities):
            count = file_entities[fpath]
            tree_lines.append(f"- `{fpath}` ({count} entities)")
        parts.append("\n".join(tree_lines) + "\n")

    if kg.relationships:
        parts.append(heading("Architecture Diagram", 2))
        mermaid = _generate_architecture_mermaid(kg)
        parts.append(fenced_code(mermaid, "mermaid"))

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )


def _generate_architecture_mermaid(kg: KnowledgeGraph) -> str:
    """Generate a Mermaid flowchart from relationships."""
    lines = ["graph TD"]
    seen_nodes: set[str] = set()
    for rel in kg.relationships[:SEQUENCE_DIAGRAM_MAX_CALLS]:
        src = _sanitize_id(rel.source_id)
        tgt = _sanitize_id(rel.target_id)
        if src not in seen_nodes:
            lines.append(f"    {src}[{_label(rel.source_id)}]")
            seen_nodes.add(src)
        if tgt not in seen_nodes:
            lines.append(f"    {tgt}[{_label(rel.target_id)}]")
            seen_nodes.add(tgt)
        arrow = (
            "-->|calls|"
            if rel.relationship_type == RelationshipType.CALLS
            else "-.->|imports|"
        )
        lines.append(f"    {src} {arrow} {tgt}")
    return "\n".join(lines)


def _sanitize_id(raw: str) -> str:
    """Make a valid Mermaid node ID."""
    return (
        raw.replace("::", "_")
        .replace(".", "_")
        .replace("/", "_")
        .replace("-", "_")
    )


def _label(raw: str) -> str:
    """Short label from an entity ID."""
    if "::" in raw:
        return raw.split("::")[-1]
    if "/" in raw:
        return raw.rsplit("/", 1)[-1]
    return raw
