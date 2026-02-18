"""Section 4 — User Stories generator."""

from __future__ import annotations

from artifactor.config import SECTION_TITLES, Settings
from artifactor.intelligence.model import IntelligenceModel
from artifactor.outputs.base import (
    SectionOutput,
    avg_confidence,
    generate_with_fallback,
    heading,
)

SECTION_NAME = "user_stories"


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
    rg = model.reasoning_graph

    parts: list[str] = [heading("User Stories")]
    confidences: list[float] = []

    if rg.rules:
        parts.append(heading("From Business Rules", 2))
        for rule in rg.rules.values():
            story = _rule_to_story(rule.rule_text, rule.rule_type)
            parts.append(f"- {story}\n")
            confidences.append(rule.confidence.value)

    if not rg.rules:
        parts.append(
            "No business rules discovered "
            "to generate user stories.\n"
        )

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )


def _rule_to_story(rule_text: str, rule_type: str) -> str:
    """Convert a business rule into a user story format."""
    type_map = {
        "validation": "data is validated correctly",
        "pricing": "pricing is calculated accurately",
        "workflow": "the workflow completes successfully",
        "access_control": "access is properly controlled",
        "data_constraint": "data integrity is maintained",
    }
    outcome = type_map.get(rule_type, "the system behaves correctly")
    return (
        f"**As a** user, **I want** {rule_text.lower()}, "
        f"**so that** {outcome}."
    )
