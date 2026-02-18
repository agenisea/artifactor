"""Tests for the confidence scorer module."""

from artifactor.analysis.quality.scorer import compute_confidence_score
from artifactor.constants import Confidence


def test_ast_only_high_confidence() -> None:
    score = compute_confidence_score(
        "function greet", ast_source=True, llm_source=False
    )
    assert score.value == Confidence.AST_ONLY
    assert score.source == "ast"


def test_llm_only_medium_confidence() -> None:
    score = compute_confidence_score(
        "business rule", ast_source=False, llm_source=True
    )
    assert score.value == Confidence.LLM_ONLY
    assert score.source == "llm"


def test_cross_validated_high_agreement() -> None:
    score = compute_confidence_score(
        "entity X",
        ast_source=True,
        llm_source=True,
        agreement="high",
    )
    assert score.value == Confidence.CROSS_VALIDATED_HIGH
    assert score.source == "cross_validated"


def test_cross_validated_medium_agreement() -> None:
    score = compute_confidence_score(
        "entity Y",
        ast_source=True,
        llm_source=True,
        agreement="medium",
    )
    assert score.value == Confidence.CROSS_VALIDATED_MEDIUM


def test_cross_validated_low_agreement() -> None:
    score = compute_confidence_score(
        "entity Z",
        ast_source=True,
        llm_source=True,
        agreement="low",
    )
    assert score.value == Confidence.CROSS_VALIDATED_LOW


def test_explanation_includes_finding() -> None:
    score = compute_confidence_score(
        "my_function", ast_source=True, llm_source=False
    )
    assert "my_function" in score.explanation
