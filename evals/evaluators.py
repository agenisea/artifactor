"""Custom pydantic-evals evaluators for Artifactor.

Tier 3 (deterministic, no LLM):
- ContainsEntities: output mentions ALL expected entity names
- SectionComplete: output contains all required subsections
- ConfidenceAbove: numeric confidence meets threshold
- OutputMatchesExpected: output contains expected_output substring

Tier 4 (agent output — AgentResponse):
- MessageContains: response.message contains expected keywords
- HasCitations: response has at least N citations
- OffTopicDecline: response declines off-topic questions

Standalone utilities (non-Evaluator):
- citation_exists: file_path exists in repo, lines in range
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from artifactor.constants import Confidence


@dataclass
class ContainsEntities(Evaluator[Any, str]):
    """Check that output contains ALL expected entity names."""

    entities: list[str] = field(default_factory=list)

    def evaluate(
        self, ctx: EvaluatorContext[Any, str]
    ) -> bool:
        output = str(ctx.output).lower()
        return all(e.lower() in output for e in self.entities)


@dataclass
class SectionComplete(Evaluator[Any, str]):
    """Check all required subsections are present in output."""

    required: list[str] = field(default_factory=list)

    def evaluate(
        self, ctx: EvaluatorContext[Any, str]
    ) -> bool:
        output = str(ctx.output).lower()
        return all(s.lower() in output for s in self.required)


@dataclass
class ConfidenceAbove(Evaluator[Any, str]):
    """Check that output contains a confidence value above threshold.

    Expects output to contain a float parseable as confidence.
    Returns the confidence as a score (0.0-1.0).
    """

    threshold: float = Confidence.GUARDRAIL_THRESHOLD

    def evaluate(
        self, ctx: EvaluatorContext[Any, str]
    ) -> float:
        try:
            value = float(ctx.output)
        except (ValueError, TypeError):
            return 0.0
        return value if value >= self.threshold else 0.0


@dataclass
class OutputMatchesExpected(Evaluator[Any, str]):
    """Check that output contains the expected_output substring."""

    def evaluate(
        self, ctx: EvaluatorContext[Any, str]
    ) -> bool:
        if ctx.expected_output is None:
            return True
        return (
            ctx.expected_output.lower()
            in str(ctx.output).lower()
        )


# ── Tier 4 evaluators (AgentResponse output) ────────────


@dataclass
class MessageContains(Evaluator[Any, Any]):
    """Check that AgentResponse.message contains ALL keywords."""

    keywords: list[str] = field(default_factory=list)

    def evaluate(
        self, ctx: EvaluatorContext[Any, Any]
    ) -> bool:
        message = getattr(ctx.output, "message", "")
        lower = message.lower()
        return all(k.lower() in lower for k in self.keywords)


@dataclass
class HasCitations(Evaluator[Any, Any]):
    """Check that AgentResponse has at least min_count citations."""

    min_count: int = 1

    def evaluate(
        self, ctx: EvaluatorContext[Any, Any]
    ) -> bool:
        citations = getattr(ctx.output, "citations", [])
        return len(citations) >= self.min_count


_CODE_GENERATION_SIGNALS = ["```", "def ", "function ", "class "]


@dataclass
class OffTopicDecline(Evaluator[Any, Any]):
    """Check that the agent declines off-topic questions.

    Verifies the response does NOT contain code suggestions
    and DOES contain a polite decline or boundary signal.
    """

    decline_signals: list[str] = field(
        default_factory=lambda: [
            "cannot",
            "don't",
            "outside",
            "boundary",
            "not able",
            "unable",
        ]
    )

    def evaluate(
        self, ctx: EvaluatorContext[Any, Any]
    ) -> bool:
        message = getattr(ctx.output, "message", "")
        lower = message.lower()
        # Should NOT contain code generation signals
        code_signals = _CODE_GENERATION_SIGNALS
        has_code = any(s in lower for s in code_signals)
        if has_code:
            return False
        # Should contain at least one decline signal
        return any(s in lower for s in self.decline_signals)


# ── Standalone utilities (not Evaluator subclasses) ──────


def citation_exists(
    file_path: str,
    line_start: int,
    line_end: int,
    repo_path: Path,
) -> tuple[bool, str]:
    """Check that a cited file exists and lines are in range.

    Returns (passed, reason) tuple.
    """
    full_path = repo_path / file_path
    if not full_path.is_file():
        return False, f"File not found: {file_path}"
    try:
        line_count = sum(
            1 for _ in full_path.open(encoding="utf-8")
        )
    except Exception as e:
        return False, f"Cannot read file: {e}"
    if line_start < 1 or line_end < line_start:
        return (
            False,
            f"Invalid line range: {line_start}-{line_end}",
        )
    if line_end > line_count:
        return (
            False,
            f"line_end ({line_end}) exceeds "
            f"file length ({line_count})",
        )
    return True, ""
