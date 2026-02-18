"""Core Intelligence Model — synthesizes analysis into queryable graphs."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from artifactor.analysis.llm.schemas import LLMAnalysisResult
from artifactor.analysis.quality.schemas import ValidationResult
from artifactor.analysis.static.schemas import (
    APIEndpoint,
    StaticAnalysisResult,
)
from artifactor.constants import (
    SHORT_ID_HEX_LENGTH,
    AnalysisSource,
    Confidence,
    ConfidenceLevel,
    RelationshipType,
    confidence_from_level,
)
from artifactor.intelligence.knowledge_graph import (
    GraphEntity,
    GraphRelationship,
    KnowledgeGraph,
)
from artifactor.intelligence.reasoning_graph import (
    InferredRisk,
    InferredRule,
    Purpose,
    ReasoningGraph,
    Workflow,
    WorkflowStep,
)
from artifactor.intelligence.value_objects import ConfidenceScore

logger = logging.getLogger(__name__)


class IntelligenceModel:
    """Central queryable model combining knowledge and reasoning graphs."""

    def __init__(
        self,
        project_id: str,
        knowledge_graph: KnowledgeGraph,
        reasoning_graph: ReasoningGraph,
    ) -> None:
        self.project_id = project_id
        self.knowledge_graph = knowledge_graph
        self.reasoning_graph = reasoning_graph
        self.created_at = datetime.now(UTC)


def build_intelligence_model(
    project_id: str,
    validation: ValidationResult,
    static: StaticAnalysisResult,
    llm: LLMAnalysisResult,
) -> IntelligenceModel:
    """Construct an IntelligenceModel from analysis outputs.

    Converts validated entities into graph nodes, adds
    relationships from call/dependency graphs, and populates
    the reasoning graph from LLM narratives and rules.
    """
    kg = KnowledgeGraph()
    rg = ReasoningGraph()

    # 1. Add validated entities as graph nodes
    for ve in validation.validated_entities:
        entity_id = _make_id(ve.file_path, ve.name)
        kg.add_entity(
            GraphEntity(
                id=entity_id,
                name=ve.name,
                entity_type=ve.entity_type,
                file_path=ve.file_path,
                start_line=ve.line,
                confidence=_source_to_confidence(
                    ve.confidence, ve.source, ve.explanation
                ),
            )
        )

    # 2. Add call graph edges — resolve to entity IDs
    for edge in static.call_graph.edges:
        source_id = _resolve_caller_id(
            edge.caller_file, edge.caller_line, kg
        )
        target_id = _resolve_callee_id(
            edge.callee, kg, edge.caller_file, edge.receiver
        )

        if source_id and target_id:
            kg.add_relationship(
                GraphRelationship(
                    id=f"call:{source_id}:{target_id}",
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=RelationshipType.CALLS,
                    weight=(
                        1.0
                        if edge.confidence == ConfidenceLevel.HIGH
                        else 0.6
                    ),
                )
            )

    # 3. Add dependency edges — resolve source to entity IDs
    for dep in static.dependency_graph.edges:
        source_entities = kg.find_by_file(
            str(dep.source_file)
        )
        source_id = (
            source_entities[0].id
            if source_entities
            else str(dep.source_file)
        )
        kg.add_relationship(
            GraphRelationship(
                id=f"import:{source_id}:{dep.target}",
                source_id=source_id,
                target_id=dep.target,
                relationship_type=RelationshipType.IMPORTS,
            )
        )

    # 3a. Add API endpoint entities from static discovery
    for ep in static.api_endpoints.endpoints:
        ep_id = _make_id(
            ep.handler_file, f"{ep.method}_{ep.path}"
        )
        kg.add_entity(
            GraphEntity(
                id=ep_id,
                name=f"{ep.method} {ep.path}",
                entity_type="endpoint",
                file_path=ep.handler_file,
                start_line=ep.handler_line,
                language="",
                signature=ep.handler_function,
                description=_format_endpoint_description(ep),
                confidence=ConfidenceScore(
                    value=Confidence.RELATIONSHIP_DEFAULT,
                    source="ast",
                    explanation="Discovered from route decorator",
                ),
            )
        )

    # 3b. Add schema entities from static discovery
    # Build name-to-id index for cross-file FK/ORM resolution
    schema_id_by_name: dict[str, str] = {}
    for schema in static.schema_map.entities:
        schema_id_by_name[schema.name] = _make_id(
            schema.file_path, f"table:{schema.name}"
        )

    for schema in static.schema_map.entities:
        schema_id = schema_id_by_name[schema.name]
        attr_summary = ", ".join(
            a.name for a in schema.attributes[:5]
        )
        if len(schema.attributes) > 5:
            attr_summary += (
                f" (+{len(schema.attributes) - 5} more)"
            )
        kg.add_entity(
            GraphEntity(
                id=schema_id,
                name=schema.name,
                entity_type="table",
                file_path=schema.file_path,
                start_line=schema.start_line,
                description=(
                    f"{schema.source_type}: {attr_summary}"
                    if attr_summary
                    else schema.source_type
                ),
                confidence=ConfidenceScore(
                    value=Confidence.RELATIONSHIP_DEFAULT,
                    source="ast",
                    explanation=(
                        f"Extracted from {schema.source_type}"
                    ),
                ),
            )
        )
        # Add FK/ORM relationships — resolve target by name index
        for rel in schema.relationships:
            target_id = schema_id_by_name.get(
                rel.target_entity,
                _make_id(
                    schema.file_path,
                    f"table:{rel.target_entity}",
                ),
            )
            kg.add_relationship(
                GraphRelationship(
                    id=(
                        f"schema_ref:{schema_id}:{target_id}"
                    ),
                    source_id=schema_id,
                    target_id=target_id,
                    relationship_type="references",
                    context=rel.relationship_type,
                )
            )

    # 4. Add purposes from LLM narratives (filter degraded results)
    quality_narratives = [
        n for n in llm.narratives if n.confidence != ConfidenceLevel.LOW
    ]
    filtered_narratives = (
        len(llm.narratives) - len(quality_narratives)
    )
    if filtered_narratives > 0:
        logger.info(
            "event=quality_gate_filtered type=narrative"
            " filtered=%d total=%d",
            filtered_narratives,
            len(llm.narratives),
        )
    for narrative in quality_narratives:
        if narrative.purpose:
            rg.add_purpose(
                Purpose(
                    entity_id=narrative.file_path,
                    statement=narrative.purpose,
                    confidence=ConfidenceScore(
                        value=confidence_from_level(
                            narrative.confidence
                        ),
                        source="llm",
                        explanation=f"Narrated: {narrative.confidence}",
                    ),
                )
            )

    # 5. Add business rules (filter degraded results)
    quality_rules = [
        r
        for r in llm.business_rules
        if r.confidence != ConfidenceLevel.LOW
    ]
    filtered_rules = (
        len(llm.business_rules) - len(quality_rules)
    )
    if filtered_rules > 0:
        logger.info(
            "event=quality_gate_filtered type=rule"
            " filtered=%d total=%d",
            filtered_rules,
            len(llm.business_rules),
        )
    for rule in quality_rules:
        rule_id = f"rule:{uuid.uuid4().hex[:SHORT_ID_HEX_LENGTH]}"
        rg.add_rule(
            InferredRule(
                id=rule_id,
                rule_text=rule.rule_text,
                rule_type=rule.rule_type,
                condition=rule.condition,
                consequence=rule.consequence,
                confidence=ConfidenceScore(
                    value=confidence_from_level(rule.confidence),
                    source="llm",
                    explanation=f"Extracted rule: {rule.confidence}",
                ),
            )
        )

    # 5b. Add risk indicators to reasoning graph (filter degraded)
    quality_risks = [
        r for r in llm.risks if r.confidence != ConfidenceLevel.LOW
    ]
    filtered_risks = len(llm.risks) - len(quality_risks)
    if filtered_risks > 0:
        logger.info(
            "event=quality_gate_filtered type=risk"
            " filtered=%d total=%d",
            filtered_risks,
            len(llm.risks),
        )
    for risk in quality_risks:
        risk_id = f"risk:{uuid.uuid4().hex[:SHORT_ID_HEX_LENGTH]}"
        rg.add_risk(
            InferredRisk(
                id=risk_id,
                title=risk.title,
                risk_type=risk.risk_type,
                severity=risk.severity,
                description=risk.description,
                file_path=risk.file_path,
                line=risk.line,
                recommendations=tuple(risk.recommendations),
                confidence=ConfidenceScore(
                    value=confidence_from_level(risk.confidence),
                    source="llm",
                    explanation=(
                        f"Detected risk: {risk.confidence}"
                    ),
                ),
            )
        )

    # 6. Infer simple workflows from call chains
    _infer_workflows(kg, rg)

    return IntelligenceModel(
        project_id=project_id,
        knowledge_graph=kg,
        reasoning_graph=rg,
    )


def _resolve_caller_id(
    file_path: str, line: int, kg: KnowledgeGraph
) -> str | None:
    """Find the entity in file_path whose line range contains `line`."""
    candidates = kg.find_by_file(file_path)
    for entity in candidates:
        end = entity.end_line or entity.start_line + 1000
        if entity.start_line <= line <= end:
            return entity.id
    # Fallback: first entity in that file
    return candidates[0].id if candidates else None


def _resolve_callee_id(
    callee_name: str,
    kg: KnowledgeGraph,
    caller_file: str = "",
    receiver: str | None = None,
) -> str | None:
    """Find entity by name with scope-aware resolution.

    Resolution priority:
    1. Qualified match: ``receiver.callee`` in any file
    2. Same-file match: entity named ``callee`` in caller's file
    3. Cross-file match: first entity named ``callee`` anywhere
    """
    # 1. Try qualified name (receiver.callee)
    if receiver:
        qualified = f"{receiver}.{callee_name}"
        for entity in kg.entities.values():
            if entity.name == qualified:
                return entity.id

    # 2. Prefer same-file match
    if caller_file:
        for entity in kg.entities.values():
            if (
                entity.name == callee_name
                and entity.file_path == caller_file
            ):
                return entity.id

    # 3. Cross-file fallback
    for entity in kg.entities.values():
        if entity.name == callee_name:
            return entity.id
    return None


def _make_id(file_path: str, name: str) -> str:
    """Generate a stable entity ID."""
    return f"{file_path}::{name}"


def _source_to_confidence(
    value: float, source: str, explanation: str
) -> ConfidenceScore:
    """Convert a source string to a typed ConfidenceScore."""
    valid: AnalysisSource
    if source == "ast":
        valid = "ast"
    elif source == "cross_validated":
        valid = "cross_validated"
    else:
        valid = "llm"
    return ConfidenceScore(
        value=value, source=valid, explanation=explanation
    )


def _format_endpoint_description(ep: APIEndpoint) -> str:
    """Build a human-readable description for an API endpoint."""
    parts = [f"{ep.method} {ep.path}"]
    if ep.parameters:
        param_names = ", ".join(p.name for p in ep.parameters)
        parts.append(f"params: {param_names}")
    if ep.response_type:
        parts.append(f"returns: {ep.response_type}")
    return " | ".join(parts)


def _infer_workflows(kg: KnowledgeGraph, rg: ReasoningGraph) -> None:
    """Infer workflows from call chains of depth >= 2."""
    for entity in kg.entities.values():
        if entity.entity_type not in ("function", "method"):
            continue
        callees = kg.get_callees(entity.id, depth=1)
        if len(callees) < 2:
            continue

        steps = [
            WorkflowStep(
                order=0,
                entity_id=entity.id,
                description=f"Entry: {entity.name}",
            ),
        ]
        for i, callee in enumerate(callees, 1):
            steps.append(
                WorkflowStep(
                    order=i,
                    entity_id=callee.id,
                    description=f"Calls {callee.name}",
                )
            )

        rg.add_workflow(
            Workflow(
                id=f"workflow:{entity.id}",
                name=f"{entity.name} workflow",
                description=(
                    f"{entity.name} calls "
                    f"{len(callees)} functions"
                ),
                steps=tuple(steps),
            )
        )
