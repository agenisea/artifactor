"""Section 8 — Interfaces generator."""

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

SECTION_NAME = "interfaces"


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

    parts: list[str] = [heading("Interface Specifications")]
    confidences: list[float] = []

    interfaces = kg.find_by_type("interface")
    classes = kg.find_by_type("class")

    if interfaces:
        parts.append(heading("Interfaces / Protocols", 2))
        rows = [
            [f"`{e.name}`", f"`{e.file_path}:{e.start_line}`",
             e.signature or "—"]
            for e in sorted(interfaces, key=lambda x: x.name)
        ]
        parts.append(table(["Name", "Location", "Signature"], rows))
        confidences.extend(
            e.confidence.value for e in interfaces
        )

    services = [
        c for c in classes
        if any(
            kw in c.name.lower()
            for kw in ("service", "repository", "handler", "controller")
        )
    ]
    if services:
        parts.append(heading("Service Boundaries", 2))
        rows = [
            [f"`{e.name}`", e.entity_type,
             f"`{e.file_path}:{e.start_line}`"]
            for e in sorted(services, key=lambda x: x.name)
        ]
        parts.append(table(["Name", "Type", "Location"], rows))
        confidences.extend(
            e.confidence.value for e in services
        )

    if not interfaces and not services:
        parts.append("No interface entities discovered.\n")

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )
