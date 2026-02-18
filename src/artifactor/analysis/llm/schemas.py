"""Pydantic models for LLM analysis output."""

from pydantic import BaseModel, Field

from artifactor.constants import ConfidenceLevel


class ModuleNarrative(BaseModel):
    """LLM-generated narrative interpretation of a code chunk."""

    file_path: str
    purpose: str = ""
    confidence: str = ConfidenceLevel.LOW
    behaviors: list[dict[str, str]] = Field(
        default_factory=lambda: list[dict[str, str]]()
    )
    business_rules: list[dict[str, str]] = Field(
        default_factory=lambda: list[dict[str, str]]()
    )
    domain_concepts: list[dict[str, str]] = Field(
        default_factory=lambda: list[dict[str, str]]()
    )
    risk_indicators: list[dict[str, str]] = Field(
        default_factory=lambda: list[dict[str, str]]()
    )
    citations: list[str] = Field(default_factory=lambda: list[str]())


class BusinessRule(BaseModel):
    """A business rule extracted from code."""

    rule_text: str
    # pricing, validation, workflow, access_control, data_constraint
    rule_type: str = "validation"
    condition: str = ""
    consequence: str = ""
    confidence: str = ConfidenceLevel.MEDIUM
    affected_entities: list[str] = Field(
        default_factory=lambda: list[str]()
    )
    citations: list[str] = Field(default_factory=lambda: list[str]())


class RiskIndicator(BaseModel):
    """A risk indicator detected in code."""

    # complexity, security, error_handling, hardcoded_value, etc.
    risk_type: str
    severity: str = ConfidenceLevel.MEDIUM
    title: str = ""
    description: str = ""
    file_path: str = ""
    line: int = 0
    recommendations: list[str] = Field(
        default_factory=lambda: list[str]()
    )
    confidence: str = ConfidenceLevel.MEDIUM


class LLMAnalysisResult(BaseModel):
    """Combined output of all LLM analysis modules."""

    narratives: list[ModuleNarrative] = Field(
        default_factory=lambda: list[ModuleNarrative]()
    )
    business_rules: list[BusinessRule] = Field(
        default_factory=lambda: list[BusinessRule]()
    )
    risks: list[RiskIndicator] = Field(
        default_factory=lambda: list[RiskIndicator]()
    )
    embeddings_stored: int = 0
    total_tokens_used: int = 0
