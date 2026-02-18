"""Section 12 — Technical User Stories generator."""

from __future__ import annotations

from artifactor.config import SECTION_TITLES, Settings
from artifactor.constants import RelationshipType
from artifactor.intelligence.model import IntelligenceModel
from artifactor.outputs.base import (
    SectionOutput,
    avg_confidence,
    generate_with_fallback,
    heading,
)

SECTION_NAME = "tech_stories"


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
    rg = model.reasoning_graph

    parts: list[str] = [heading("Technical User Stories")]
    confidences: list[float] = []

    call_rels = [
        r for r in kg.relationships
        if r.relationship_type == RelationshipType.CALLS
    ]
    if call_rels:
        parts.append(heading("From Call Chains", 2))
        for rel in call_rels[:15]:
            story = (
                f"**As a** developer, **I need** `{rel.source_id}` "
                f"to call `{rel.target_id}`, "
                f"**so that** the call chain is maintained."
            )
            parts.append(f"- {story}\n")

    if rg.workflows:
        parts.append(heading("From Workflows", 2))
        for wf in rg.workflows:
            parts.append(f"### {wf.name}\n")
            for step in wf.steps:
                parts.append(
                    f"- Step {step.order}: "
                    f"`{step.entity_id}` — {step.description}\n"
                )
            confidences.append(wf.confidence.value)

    if not call_rels and not rg.workflows:
        parts.append(
            "No technical stories could be generated.\n"
        )

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )
