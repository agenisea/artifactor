"""Section 3 — Personas generator."""

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

SECTION_NAME = "personas"

_ADMIN_KEYWORDS = {"admin", "manage", "dashboard", "config", "setting"}
_DEV_KEYWORDS = {"api", "sdk", "webhook", "endpoint", "token"}
_USER_KEYWORDS = {"login", "register", "profile", "account", "submit"}


def _detect_personas(
    entity_names: list[str],
) -> dict[str, list[str]]:
    """Detect personas from entity name patterns."""
    personas: dict[str, list[str]] = {}
    for name in entity_names:
        lower = name.lower()
        if any(kw in lower for kw in _ADMIN_KEYWORDS):
            personas.setdefault("Administrator", []).append(name)
        if any(kw in lower for kw in _DEV_KEYWORDS):
            personas.setdefault("Developer", []).append(name)
        if any(kw in lower for kw in _USER_KEYWORDS):
            personas.setdefault("End User", []).append(name)
    return personas


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

    parts: list[str] = [heading("User Personas")]

    entity_names = [e.name for e in kg.entities.values()]
    detected = _detect_personas(entity_names)

    if not detected:
        detected["General User"] = []

    confidences: list[float] = []
    for persona_name, related_entities in sorted(detected.items()):
        parts.append(heading(persona_name, 2))

        if related_entities:
            parts.append(heading("System Interactions", 3))
            parts.append(
                bullet_list(
                    [f"`{e}`" for e in related_entities[:10]]
                )
            )

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )
