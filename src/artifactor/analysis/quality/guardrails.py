"""Guardrails: citation verification, input validation, confidence gating."""

from __future__ import annotations

import logging
from pathlib import Path

from artifactor.analysis.quality.schemas import (
    GuardrailResult,
)
from artifactor.constants import Confidence
from artifactor.intelligence.value_objects import Citation

logger = logging.getLogger(__name__)

_MAX_CHAT_INPUT_LENGTH = 10_000


def verify_citations(
    citations: list[Citation],
    repo_path: Path,
) -> list[GuardrailResult]:
    """Validate citations against the analyzed repository.

    Checks:
    1. file_path exists in repo
    2. line_start >= 1
    3. line_end >= line_start
    4. line_end <= file's total line count
    """
    results: list[GuardrailResult] = []
    for citation in citations:
        result = _check_single_citation(citation, repo_path)
        results.append(result)
    return results


def _check_single_citation(
    citation: Citation, repo_path: Path
) -> GuardrailResult:
    """Check a single citation for validity."""
    file_path = repo_path / citation.file_path
    label = f"{citation.file_path}:{citation.line_start}"

    if not file_path.is_file():
        return GuardrailResult(
            check_name="citation_file_exists",
            passed=False,
            reason=f"File not found: {citation.file_path}",
        )

    if citation.line_start < 1:
        return GuardrailResult(
            check_name="citation_line_start",
            passed=False,
            reason=f"line_start < 1 in {label}",
        )

    if citation.line_end < citation.line_start:
        return GuardrailResult(
            check_name="citation_line_range",
            passed=False,
            reason=(
                f"line_end < line_start in {label}"
            ),
        )

    try:
        line_count = sum(
            1 for _ in file_path.open(encoding="utf-8")
        )
    except Exception:
        return GuardrailResult(
            check_name="citation_file_readable",
            passed=False,
            reason=f"Cannot read file: {citation.file_path}",
        )

    if citation.line_end > line_count:
        return GuardrailResult(
            check_name="citation_line_end",
            passed=False,
            reason=(
                f"line_end ({citation.line_end}) exceeds "
                f"file length ({line_count}) in {label}"
            ),
        )

    return GuardrailResult(
        check_name="citation_valid",
        passed=True,
    )


def validate_chat_input(query: str) -> str:
    """Sanitize and enforce length limits on chat input.

    Raises ValueError if input is empty after stripping.
    """
    cleaned = query.strip()
    if not cleaned:
        msg = "Chat input is empty"
        raise ValueError(msg)

    if len(cleaned) > _MAX_CHAT_INPUT_LENGTH:
        cleaned = cleaned[:_MAX_CHAT_INPUT_LENGTH]

    return cleaned


def gate_low_confidence_output(
    content: str,
    confidence: float,
    threshold: float = Confidence.GUARDRAIL_THRESHOLD,
) -> tuple[str, bool]:
    """Prepend a disclaimer if confidence is below threshold.

    Returns (possibly-prefixed content, whether gated).
    """
    if confidence >= threshold:
        return content, False

    disclaimer = (
        f"[Low confidence: {confidence:.2f}] "
    )
    return disclaimer + content, True
