"""Reasoning graph: inferred purpose, rules, and workflows."""

from __future__ import annotations

from dataclasses import dataclass, field

from artifactor.constants import Confidence
from artifactor.intelligence.value_objects import (
    Citation,
    ConfidenceScore,
)


@dataclass(frozen=True)
class Purpose:
    """Why a code entity exists."""

    entity_id: str
    statement: str
    confidence: ConfidenceScore = field(
        default_factory=lambda: ConfidenceScore(
            value=Confidence.LLM_ONLY, source="llm", explanation=""
        )
    )
    business_context: str | None = None
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True)
class InferredRule:
    """A business rule inferred from code analysis."""

    id: str
    rule_text: str
    rule_type: str = "validation"
    affected_entity_ids: tuple[str, ...] = ()
    condition: str = ""
    consequence: str = ""
    confidence: ConfidenceScore = field(
        default_factory=lambda: ConfidenceScore(
            value=Confidence.LLM_ONLY, source="llm", explanation=""
        )
    )
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True)
class WorkflowStep:
    """A single step in a workflow."""

    order: int
    entity_id: str
    description: str


@dataclass(frozen=True)
class Workflow:
    """A multi-step process inferred from call chains."""

    id: str
    name: str
    description: str = ""
    steps: tuple[WorkflowStep, ...] = ()
    confidence: ConfidenceScore = field(
        default_factory=lambda: ConfidenceScore(
            value=Confidence.WORKFLOW_DEFAULT, source="llm", explanation=""
        )
    )


@dataclass(frozen=True)
class InferredRisk:
    """A risk indicator inferred from code analysis."""

    id: str
    title: str
    risk_type: str = "complexity"
    severity: str = "medium"
    description: str = ""
    file_path: str = ""
    line: int = 0
    recommendations: tuple[str, ...] = ()
    confidence: ConfidenceScore = field(
        default_factory=lambda: ConfidenceScore(
            value=Confidence.LLM_ONLY, source="llm", explanation=""
        )
    )


@dataclass
class ReasoningGraph:
    """Graph of inferred purposes, rules, and workflows."""

    purposes: dict[str, Purpose] = field(
        default_factory=lambda: dict[str, Purpose]()
    )
    rules: dict[str, InferredRule] = field(
        default_factory=lambda: dict[str, InferredRule]()
    )
    workflows: list[Workflow] = field(
        default_factory=lambda: list[Workflow]()
    )
    risks: dict[str, InferredRisk] = field(
        default_factory=lambda: dict[str, InferredRisk]()
    )

    def add_purpose(self, purpose: Purpose) -> None:
        """Set the purpose for an entity."""
        self.purposes[purpose.entity_id] = purpose

    def add_rule(self, rule: InferredRule) -> None:
        """Add a business rule."""
        self.rules[rule.id] = rule

    def add_workflow(self, workflow: Workflow) -> None:
        """Add a workflow."""
        self.workflows.append(workflow)

    def add_risk(self, risk: InferredRisk) -> None:
        """Add a risk indicator."""
        self.risks[risk.id] = risk

    def get_purpose(
        self, entity_id: str
    ) -> Purpose | None:
        """Get the purpose for an entity."""
        return self.purposes.get(entity_id)

    def get_rules_for_entity(
        self, entity_id: str
    ) -> list[InferredRule]:
        """Get rules that affect a given entity."""
        return [
            r
            for r in self.rules.values()
            if entity_id in r.affected_entity_ids
        ]

    def get_risks_by_file(
        self, file_path: str
    ) -> list[InferredRisk]:
        """Get risks for a specific file."""
        return [
            r
            for r in self.risks.values()
            if r.file_path == file_path
        ]
