"""Section 2 — Features generator."""

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

SECTION_NAME = "features"


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

    parts: list[str] = [heading("Main Application Features")]

    files: dict[str, list[str]] = {}
    confidences: list[float] = []
    for entity in kg.entities.values():
        if entity.entity_type in ("function", "method"):
            files.setdefault(entity.file_path, []).append(
                entity.name
            )
            confidences.append(entity.confidence.value)

    rows: list[list[str]] = []
    for fpath in sorted(files):
        purpose = rg.get_purpose(fpath)
        purpose_text = purpose.statement if purpose else "—"
        names = files[fpath]
        rows.append(
            [
                f"`{fpath}`",
                purpose_text,
                str(len(names)),
            ]
        )

    if rows:
        parts.append(heading("Feature Areas", 2))
        parts.append(
            table(
                ["File", "Purpose", "Entities"],
                rows,
            )
        )

    functions = kg.find_by_type("function")
    if functions:
        parts.append(heading("Functions", 2))
        func_rows = [
            [
                f"`{f.name}`",
                f"`{f.file_path}`",
                f.signature or "—",
            ]
            for f in sorted(functions, key=lambda e: e.name)
        ]
        parts.append(
            table(
                ["Name", "File", "Signature"],
                func_rows,
            )
        )

    content = "\n".join(parts)
    return SectionOutput(
        title=SECTION_TITLES[SECTION_NAME],
        section_name=SECTION_NAME,
        content=content,
        confidence=avg_confidence(confidences),
    )
