"""Citation verification and formatting for chat responses.

Delegates to the guardrails module for mechanical checks,
then formats citations for display.
"""

from __future__ import annotations

from pathlib import Path

from artifactor.analysis.quality.guardrails import (
    verify_citations as guardrail_verify,
)
from artifactor.analysis.quality.schemas import (
    GuardrailResult,
)
from artifactor.intelligence.value_objects import Citation


def verify_citations(
    citations: list[Citation],
    repo_path: Path,
) -> list[GuardrailResult]:
    """Verify all citations against the repository.

    Delegates to the guardrails module. Returns a list of
    GuardrailResult (one per citation).
    """
    return guardrail_verify(citations, repo_path)


def format_citation(citation: Citation) -> str:
    """Format a single citation as a readable string.

    Example: `main.py:10-25 (login_handler, confidence: 0.90)`
    """
    parts = [f"{citation.file_path}:{citation.line_start}"]
    if citation.line_end != citation.line_start:
        parts[0] += f"-{citation.line_end}"
    extras: list[str] = []
    if citation.function_name:
        extras.append(citation.function_name)
    extras.append(f"confidence: {citation.confidence:.2f}")
    return f"{parts[0]} ({', '.join(extras)})"


def format_citations_block(
    citations: list[Citation],
) -> str:
    """Format multiple citations as a markdown block.

    Returns empty string if no citations.
    """
    if not citations:
        return ""
    lines = ["**Sources:**"]
    for i, citation in enumerate(citations, 1):
        lines.append(f"{i}. {format_citation(citation)}")
    return "\n".join(lines)


def filter_valid_citations(
    citations: list[Citation],
    repo_path: Path,
) -> list[Citation]:
    """Return only citations that pass verification."""
    results = verify_citations(citations, repo_path)
    return [
        citation
        for citation, result in zip(
            citations, results, strict=True
        )
        if result.passed
    ]
