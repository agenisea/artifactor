"""Section 5 — Security Requirements generator."""

from __future__ import annotations

from artifactor.config import SECTION_TITLES, Settings
from artifactor.intelligence.model import IntelligenceModel
from artifactor.outputs.base import (
    SectionOutput,
    avg_confidence,
    bullet_list,
    generate_with_fallback,
    heading,
    table,
)

SECTION_NAME = "security_requirements"

_AUTH_KEYWORDS = {
    "auth", "login", "logout", "token", "jwt",
    "oauth", "session", "password", "credential",
}
_AUTHZ_KEYWORDS = {
    "permission", "role", "rbac", "scope",
    "access", "policy", "guard", "middleware",
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
    rg = model.reasoning_graph

    parts: list[str] = [heading("Security Requirements")]
    confidences: list[float] = []

    auth_entities = [
        e for e in kg.entities.values()
        if any(kw in e.name.lower() for kw in _AUTH_KEYWORDS)
    ]
    if auth_entities:
        parts.append(heading("Authentication", 2))
        rows = [
            [f"`{e.name}`", e.entity_type,
             f"`{e.file_path}:{e.start_line}`"]
            for e in auth_entities
        ]
        parts.append(table(["Entity", "Type", "Location"], rows))
        confidences.extend(
            e.confidence.value for e in auth_entities
        )

    authz_entities = [
        e for e in kg.entities.values()
        if any(kw in e.name.lower() for kw in _AUTHZ_KEYWORDS)
    ]
    if authz_entities:
        parts.append(heading("Authorization", 2))
        rows = [
            [f"`{e.name}`", e.entity_type,
             f"`{e.file_path}:{e.start_line}`"]
            for e in authz_entities
        ]
        parts.append(table(["Entity", "Type", "Location"], rows))
        confidences.extend(
            e.confidence.value for e in authz_entities
        )

    security_rules = [
        r for r in rg.rules.values()
        if r.rule_type == "access_control"
    ]
    if security_rules:
        parts.append(heading("Access Control Rules", 2))
        parts.append(
            bullet_list([r.rule_text for r in security_rules])
        )
        confidences.extend(
            r.confidence.value for r in security_rules
        )

    if not auth_entities and not authz_entities and not security_rules:
        parts.append(
            "No authentication or authorization patterns "
            "discovered in the codebase.\n"
        )

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )
