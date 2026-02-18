"""Section 10 — API Specifications generator."""

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

SECTION_NAME = "api_specs"


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

    parts: list[str] = [heading("API Specifications")]
    confidences: list[float] = []

    endpoints = kg.find_by_type("endpoint")

    if endpoints:
        parts.append(heading("Endpoints", 2))
        rows = [
            [f"`{e.name}`", f"`{e.file_path}:{e.start_line}`",
             e.signature or "—", e.description or "—"]
            for e in sorted(endpoints, key=lambda x: x.name)
        ]
        parts.append(
            table(
                ["Endpoint", "Location", "Signature", "Description"],
                rows,
            )
        )
        confidences.extend(
            e.confidence.value for e in endpoints
        )

    route_funcs = [
        e for e in kg.entities.values()
        if e.entity_type == "function"
        and any(
            kw in e.name.lower()
            for kw in ("route", "handler", "endpoint", "view")
        )
    ]
    if route_funcs:
        parts.append(heading("Route Handlers", 2))
        rows = [
            [f"`{e.name}`", f"`{e.file_path}:{e.start_line}`",
             e.signature or "—"]
            for e in sorted(route_funcs, key=lambda x: x.name)
        ]
        parts.append(
            table(["Handler", "Location", "Signature"], rows)
        )
        confidences.extend(
            e.confidence.value for e in route_funcs
        )

    if not endpoints and not route_funcs:
        parts.append(
            "No API endpoints or route handlers "
            "discovered in the codebase.\n"
        )

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )
