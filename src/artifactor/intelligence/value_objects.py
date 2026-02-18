"""Frozen, identity-less domain types shared across all layers.

These are the vocabulary of the system. Defined once here, used everywhere.
Raw strings and integers are never used to represent file paths in citations,
confidence levels, or entity classifications in analysis output, API responses,
MCP tool returns, or chat citations.
"""

from dataclasses import dataclass

from artifactor.constants import AnalysisSource


@dataclass(frozen=True)
class Citation:
    """Immutable reference to a specific source code location.

    Every generated claim must be accompanied by at least one Citation.
    Verified mechanically: file must exist, line must be in range.
    """

    file_path: str
    function_name: str | None
    line_start: int
    line_end: int
    confidence: float  # 0.0 to 1.0


@dataclass(frozen=True)
class ConfidenceScore:
    """Quality rating assigned to a generated insight."""

    value: float  # 0.0 to 1.0
    source: AnalysisSource
    explanation: str
