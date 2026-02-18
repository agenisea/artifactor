"""Mermaid syntax generators from Intelligence Model data."""

from __future__ import annotations

from artifactor.constants import (
    ARCH_DIAGRAM_MAX_ENTITIES,
    ARCH_DIAGRAM_MAX_RELATIONSHIPS,
    SEQUENCE_DIAGRAM_MAX_CALLS,
    RelationshipType,
)
from artifactor.intelligence.knowledge_graph import (
    GraphEntity,
    KnowledgeGraph,
)
from artifactor.intelligence.reasoning_graph import (
    Workflow,
)


def generate_architecture_diagram(kg: KnowledgeGraph) -> str:
    """Generate a Mermaid flowchart for system architecture."""
    lines = ["graph TD"]
    seen: set[str] = set()

    for rel in kg.relationships[:ARCH_DIAGRAM_MAX_RELATIONSHIPS]:
        src = _safe_id(rel.source_id)
        tgt = _safe_id(rel.target_id)
        if src not in seen:
            lines.append(
                f"    {src}[{_label(rel.source_id)}]"
            )
            seen.add(src)
        if tgt not in seen:
            lines.append(
                f"    {tgt}[{_label(rel.target_id)}]"
            )
            seen.add(tgt)
        arrow = _arrow(rel.relationship_type)
        lines.append(f"    {src} {arrow} {tgt}")

    if len(lines) == 1:
        # No relationships — show entities only
        for entity in list(kg.entities.values())[:ARCH_DIAGRAM_MAX_ENTITIES]:
            eid = _safe_id(entity.id)
            lines.append(f"    {eid}[{entity.name}]")

    return "\n".join(lines)


def generate_er_diagram(kg: KnowledgeGraph) -> str:
    """Generate a Mermaid ER diagram from class/table entities."""
    lines = ["erDiagram"]
    data_entities = kg.find_by_type("class") + kg.find_by_type(
        "table"
    )
    entity_ids = {e.id for e in data_entities}

    for entity in data_entities:
        safe = entity.name.replace(" ", "_")
        lines.append(f"    {safe} {{")
        lines.append("        string id")
        lines.append("    }")

    for rel in kg.relationships:
        if (
            rel.source_id in entity_ids
            and rel.target_id in entity_ids
        ):
            src = _entity_name(rel.source_id, data_entities)
            tgt = _entity_name(rel.target_id, data_entities)
            lines.append(
                f"    {src} ||--o{{ {tgt} : "
                f'"{rel.relationship_type}"'
            )

    return "\n".join(lines)


def generate_call_graph_diagram(
    kg: KnowledgeGraph,
    entity_id: str | None = None,
    depth: int = 2,
) -> str:
    """Generate a Mermaid flowchart for call graph."""
    lines = ["flowchart LR"]
    seen: set[str] = set()

    call_rels = [
        r
        for r in kg.relationships
        if r.relationship_type == RelationshipType.CALLS
    ]

    if entity_id:
        # Focus on a specific entity
        relevant = [
            r
            for r in call_rels
            if r.source_id == entity_id
            or r.target_id == entity_id
        ]
    else:
        relevant = call_rels[:SEQUENCE_DIAGRAM_MAX_CALLS]

    for rel in relevant:
        src = _safe_id(rel.source_id)
        tgt = _safe_id(rel.target_id)
        if src not in seen:
            lines.append(
                f"    {src}[{_label(rel.source_id)}]"
            )
            seen.add(src)
        if tgt not in seen:
            lines.append(
                f"    {tgt}[{_label(rel.target_id)}]"
            )
            seen.add(tgt)
        lines.append(f"    {src} --> {tgt}")

    return "\n".join(lines)


def generate_sequence_diagram(workflow: Workflow) -> str:
    """Generate a Mermaid sequence diagram from a workflow."""
    lines = ["sequenceDiagram"]
    if not workflow.steps:
        return "\n".join(lines)

    # Declare participants
    participants: list[str] = []
    for step in workflow.steps:
        label = _label(step.entity_id)
        if label not in participants:
            participants.append(label)
            lines.append(f"    participant {label}")

    # Add arrows between consecutive steps
    for i in range(len(workflow.steps) - 1):
        src = _label(workflow.steps[i].entity_id)
        tgt = _label(workflow.steps[i + 1].entity_id)
        desc = workflow.steps[i + 1].description
        lines.append(f"    {src}->>+{tgt}: {desc}")

    return "\n".join(lines)


def generate_sequence_diagram_from_calls(
    kg: KnowledgeGraph,
) -> str:
    """Generate a Mermaid sequence diagram from call relationships.

    Uses the first 30 call relationships by storage order.
    A smarter heuristic (group by entry point, prefer deeper
    chains) can replace this slice later.
    """
    call_rels = [
        r
        for r in kg.relationships
        if r.relationship_type == RelationshipType.CALLS
    ][:SEQUENCE_DIAGRAM_MAX_CALLS]

    if not call_rels:
        return "sequenceDiagram"

    lines = ["sequenceDiagram"]

    # Collect participants in first-appearance order
    participants: list[str] = []
    for rel in call_rels:
        src = _label(rel.source_id)
        tgt = _label(rel.target_id)
        if src not in participants:
            participants.append(src)
        if tgt not in participants:
            participants.append(tgt)

    for p in participants:
        lines.append(f"    participant {p}")

    for rel in call_rels:
        src = _label(rel.source_id)
        tgt = _label(rel.target_id)
        lines.append(f"    {src}->>{tgt}: calls")

    return "\n".join(lines)


def _safe_id(raw: str) -> str:
    """Make a valid Mermaid node ID."""
    return (
        raw.replace("::", "_")
        .replace(".", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(" ", "_")
    )


def _label(raw: str) -> str:
    """Short display label from an entity ID."""
    if "::" in raw:
        return raw.split("::")[-1]
    if "/" in raw:
        return raw.rsplit("/", 1)[-1]
    return raw


def _arrow(rel_type: str) -> str:
    """Mermaid arrow style for relationship type."""
    arrows: dict[str, str] = {
        RelationshipType.CALLS: "-->",
        RelationshipType.IMPORTS: "-.->",
        RelationshipType.INHERITS: "==>",
        RelationshipType.USES: "-->",
    }
    return arrows.get(rel_type, "-->")


def _entity_name(
    entity_id: str,
    entities: list[GraphEntity],
) -> str:
    """Look up display name for an entity."""
    for e in entities:
        if e.id == entity_id:
            return e.name.replace(" ", "_")
    return _label(entity_id)
