"""Section 13 — Security Considerations generator."""

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

SECTION_NAME = "security_considerations"

_VULNERABILITY_KEYWORDS = {
    "eval", "exec", "system", "popen", "subprocess",
    "shell", "pickle", "deserialize", "unsafe",
    "raw_sql", "sql", "inject",
}
_SENSITIVE_KEYWORDS = {
    "password", "secret", "key", "token",
    "credential", "private",
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

    parts: list[str] = [heading("Security Considerations")]
    confidences: list[float] = []

    vuln_entities = [
        e for e in kg.entities.values()
        if any(
            kw in e.name.lower()
            for kw in _VULNERABILITY_KEYWORDS
        )
    ]
    if vuln_entities:
        parts.append(heading("Potential Vulnerability Patterns", 2))
        rows = [
            [f"`{e.name}`", e.entity_type,
             f"`{e.file_path}:{e.start_line}`"]
            for e in vuln_entities
        ]
        parts.append(table(["Entity", "Type", "Location"], rows))
        confidences.extend(
            e.confidence.value for e in vuln_entities
        )

    sensitive_entities = [
        e for e in kg.entities.values()
        if any(
            kw in e.name.lower()
            for kw in _SENSITIVE_KEYWORDS
        )
    ]
    if sensitive_entities:
        parts.append(heading("Sensitive Data Handlers", 2))
        rows = [
            [f"`{e.name}`", f"`{e.file_path}:{e.start_line}`"]
            for e in sensitive_entities
        ]
        parts.append(table(["Entity", "Location"], rows))

    if rg.risks:
        parts.append(heading("LLM-Detected Risks", 2))
        rows = [
            [r.title, r.severity, r.risk_type,
             f"`{r.file_path}:{r.line}`"]
            for r in rg.risks.values()
        ]
        parts.append(
            table(
                ["Risk", "Severity", "Type", "Location"],
                rows,
            )
        )
        confidences.extend(
            r.confidence.value for r in rg.risks.values()
        )

    parts.append(heading("Coverage Summary", 2))
    has_auth = any(
        any(
            kw in e.name.lower()
            for kw in ("auth", "login", "session")
        )
        for e in kg.entities.values()
    )
    has_validation = any(
        r.rule_type == "validation"
        for r in rg.rules.values()
    )
    checks = [
        f"Authentication entities: "
        f"{'Found' if has_auth else 'Not found'}",
        f"Validation rules: "
        f"{'Found' if has_validation else 'Not found'}",
        f"Sensitive data handlers: "
        f"{len(sensitive_entities)} found",
        f"Potential vulnerability patterns: "
        f"{len(vuln_entities)} found",
    ]
    parts.append(bullet_list(checks))

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )
