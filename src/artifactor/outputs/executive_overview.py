"""Section 1 — Executive Overview generator."""

from __future__ import annotations

from artifactor.config import SECTION_TITLES, Settings
from artifactor.intelligence.model import IntelligenceModel
from artifactor.outputs.base import (
    SectionOutput,
    avg_confidence,
    bullet_list,
    generate_with_fallback,
    heading,
)

SECTION_NAME = "executive_overview"


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

    parts: list[str] = [heading("Executive Overview")]

    purposes = list(rg.purposes.values())
    if purposes:
        parts.append(
            f"**Summary:** {purposes[0].statement}\n"
        )

    entity_types: dict[str, int] = {}
    languages: set[str] = set()
    files: set[str] = set()
    for entity in kg.entities.values():
        entity_types[entity.entity_type] = (
            entity_types.get(entity.entity_type, 0) + 1
        )
        if entity.language:
            languages.add(entity.language)
        files.add(entity.file_path)

    parts.append(heading("At a Glance", 2))
    stats = [
        f"**Entities:** {len(kg.entities)}",
        f"**Files:** {len(files)}",
        f"**Languages:** {len(languages)}",
        f"**Rules:** {len(rg.rules)}",
        f"**Workflows:** {len(rg.workflows)}",
    ]
    parts.append(bullet_list(stats))

    confidences = [
        p.confidence.value for p in purposes
    ]
    content = "\n".join(parts)

    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )
