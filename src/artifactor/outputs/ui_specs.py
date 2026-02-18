"""Section 9 — UI Specifications generator."""

from __future__ import annotations

from artifactor.config import SECTION_TITLES, Settings
from artifactor.intelligence.model import IntelligenceModel
from artifactor.outputs.base import (
    SectionOutput,
    avg_confidence,
    generate_with_fallback,
    heading,
    table,
)

SECTION_NAME = "ui_specs"

_UI_KEYWORDS = {
    "component", "page", "view", "screen", "form",
    "modal", "dialog", "button", "input", "layout",
    "template", "widget",
}


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

    parts: list[str] = [heading("UI Specifications")]
    confidences: list[float] = []

    ui_entities = [
        e for e in kg.entities.values()
        if any(kw in e.name.lower() for kw in _UI_KEYWORDS)
        or any(
            ext in e.file_path
            for ext in (".tsx", ".jsx", ".vue", ".svelte")
        )
    ]

    if ui_entities:
        parts.append(heading("Screens / Components", 2))
        rows = [
            [f"`{e.name}`", e.entity_type,
             f"`{e.file_path}`", e.language or "—"]
            for e in sorted(ui_entities, key=lambda x: x.name)
        ]
        parts.append(
            table(["Name", "Type", "File", "Language"], rows)
        )
        confidences.extend(
            e.confidence.value for e in ui_entities
        )

        parts.append(heading("Summary", 2))
        parts.append(
            f"**{len(ui_entities)}** UI components/screens "
            f"identified.\n"
        )
    else:
        parts.append(
            "No UI components or frontend entities "
            "discovered in the codebase.\n"
        )

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )
