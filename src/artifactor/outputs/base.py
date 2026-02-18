"""Base types and helpers for section generators."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from artifactor.config import SECTION_TITLES, Settings
from artifactor.constants import (
    ERROR_TRUNCATION_CHARS,
    MIN_CONTEXT_ITEMS,
    Confidence,
)
from artifactor.intelligence.model import IntelligenceModel
from artifactor.intelligence.value_objects import Citation
from artifactor.outputs.section_prompts import (
    CONTEXT_BUILDERS,
    SECTION_SYSTEM_PROMPTS,
    count_context_items,
)
from artifactor.outputs.synthesizer import synthesize_section

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SectionOutput:
    """Result of a section generator."""

    title: str
    section_name: str
    content: str  # Markdown
    confidence: float = 0.0
    citations: tuple[Citation, ...] = ()


class SectionGenerator(Protocol):
    """Interface every section generator must satisfy."""

    section_name: str

    async def generate(
        self,
        model: IntelligenceModel,
        project_id: str,
        settings: Settings,
    ) -> SectionOutput: ...


# ── Markdown formatting helpers ──────────────────────────────


def heading(text: str, level: int = 1) -> str:
    """Return a Markdown heading."""
    return f"{'#' * level} {text}\n"


def table(headers: list[str], rows: list[list[str]]) -> str:
    """Return a Markdown table."""
    if not headers:
        return ""
    lines: list[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(lines) + "\n"


def bullet_list(items: list[str]) -> str:
    """Return a Markdown bullet list."""
    if not items:
        return ""
    return "\n".join(f"- {item}" for item in items) + "\n"


def fenced_code(content: str, language: str = "") -> str:
    """Return a Markdown fenced code block."""
    return f"```{language}\n{content}\n```\n"


def make_degraded_section(
    section_name: str, error: str
) -> SectionOutput:
    """Create a placeholder section when generation fails.

    Pure function — no side effects. Used by the pipeline to
    provide partial results instead of dropping failed sections.
    """
    title = SECTION_TITLES.get(
        section_name, section_name.replace("_", " ").title()
    )
    return SectionOutput(
        title=title,
        section_name=section_name,
        content=(
            f"# {title}\n\n"
            f"*This section could not be generated."
            f" Error: {error[:ERROR_TRUNCATION_CHARS]}*\n"
        ),
        confidence=0.0,
    )


def avg_confidence(values: list[float]) -> float:
    """Average of confidence values, or 0 if empty."""
    if not values:
        return 0.0
    return sum(values) / len(values)


# ── Shared generation logic ─────────────────────────────


async def generate_with_fallback(
    section_name: str,
    model: IntelligenceModel,
    project_id: str,
    settings: Settings,
    template_fn: Callable[
        [IntelligenceModel, str], SectionOutput
    ],
) -> SectionOutput:
    """LLM-powered section generation with template fallback.

    Shared by all 13 section generators. Eliminates duplicated
    boilerplate: prompt lookup -> context build -> synthesize
    -> confidence scoring -> template fallback.
    """
    system_prompt = SECTION_SYSTEM_PROMPTS.get(section_name)
    context_builder = CONTEXT_BUILDERS.get(section_name)

    if system_prompt and context_builder:
        context_data = context_builder(model)
        item_count = count_context_items(context_data)
        result = await synthesize_section(
            section_name,
            system_prompt,
            context_data,
            settings,
            context_item_count=item_count,
        )
        if result is not None:
            logger.info(
                "event=section_synthesized section=%s"
                " model=%s tokens=%d",
                section_name,
                result.model_used,
                result.input_tokens + result.output_tokens,
            )
            base = (
                Confidence.LLM_SECTION_RICH
                if item_count >= MIN_CONTEXT_ITEMS
                else Confidence.LLM_SECTION_SPARSE
            )
            return SectionOutput(
                title=SECTION_TITLES[section_name],
                section_name=section_name,
                content=result.content,
                confidence=base,
            )

    logger.info(
        "event=section_fallback_template section=%s",
        section_name,
    )
    return template_fn(model, project_id)
