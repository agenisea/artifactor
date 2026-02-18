"""Assign confidence scores to analysis outputs."""

from __future__ import annotations

from typing import Literal

from artifactor.constants import Confidence, ConfidenceLevel
from artifactor.intelligence.value_objects import ConfidenceScore


def compute_confidence_score(
    finding: str,
    ast_source: bool,
    llm_source: bool,
    agreement: Literal["high", "medium", "low"] = "medium",
) -> ConfidenceScore:
    """Compute a confidence score based on source and agreement.

    Scoring rules:
    - AST-only: 0.9 (deterministic parser)
    - LLM-only: 0.7 (probabilistic inference)
    - Both agree (cross-validated): 0.95
    - Both disagree: 0.5
    """
    if ast_source and llm_source:
        if agreement == ConfidenceLevel.HIGH:
            return ConfidenceScore(
                value=Confidence.CROSS_VALIDATED_HIGH,
                source="cross_validated",
                explanation=(
                    f"Cross-validated: AST and LLM agree "
                    f"on '{finding}'"
                ),
            )
        if agreement == ConfidenceLevel.MEDIUM:
            return ConfidenceScore(
                value=Confidence.CROSS_VALIDATED_MEDIUM,
                source="cross_validated",
                explanation=(
                    f"Partial agreement on '{finding}'"
                ),
            )
        return ConfidenceScore(
            value=Confidence.CROSS_VALIDATED_LOW,
            source="cross_validated",
            explanation=(
                f"AST and LLM disagree on '{finding}'"
            ),
        )

    if ast_source:
        return ConfidenceScore(
            value=Confidence.AST_ONLY,
            source="ast",
            explanation=(
                f"AST-derived (deterministic): '{finding}'"
            ),
        )

    return ConfidenceScore(
        value=Confidence.LLM_ONLY,
        source="llm",
        explanation=(
            f"LLM-inferred (probabilistic): '{finding}'"
        ),
    )
