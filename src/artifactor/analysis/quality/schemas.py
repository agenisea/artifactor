"""Pydantic models for quality assurance output."""

from __future__ import annotations

from pydantic import BaseModel, Field

from artifactor.constants import Confidence


class GuardrailResult(BaseModel):
    """Outcome of a single guardrail check."""

    check_name: str
    passed: bool
    reason: str | None = None


class ValidatedEntity(BaseModel):
    """An entity that has passed cross-validation."""

    name: str
    entity_type: str
    file_path: str
    line: int = 0
    source: str = "ast"  # "ast", "llm", "cross_validated"
    confidence: float = Confidence.AST_ONLY
    explanation: str = ""


class ValidationResult(BaseModel):
    """Output of cross-validation between static and LLM analysis."""

    validated_entities: list[ValidatedEntity] = Field(
        default_factory=lambda: list[ValidatedEntity]()
    )
    conflicts: list[str] = Field(
        default_factory=lambda: list[str]()
    )
    ast_only_count: int = 0
    llm_only_count: int = 0
    cross_validated_count: int = 0


class QualityReport(BaseModel):
    """Summary of quality checks on analysis output."""

    guardrail_results: list[GuardrailResult] = Field(
        default_factory=lambda: list[GuardrailResult]()
    )
    citations_checked: int = 0
    citations_valid: int = 0
    avg_confidence: float = 0.0
