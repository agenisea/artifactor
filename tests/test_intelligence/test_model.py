"""Tests for the Intelligence Model builder."""

from artifactor.analysis.llm.schemas import (
    BusinessRule,
    LLMAnalysisResult,
    ModuleNarrative,
    RiskIndicator,
)
from artifactor.analysis.quality.schemas import (
    ValidatedEntity,
    ValidationResult,
)
from artifactor.analysis.static.schemas import (
    APIEndpoint,
    APIEndpoints,
    APIParameter,
    ASTForest,
    CallEdge,
    CallGraph,
    DependencyEdge,
    DependencyGraph,
    SchemaAttribute,
    SchemaEntity,
    SchemaMap,
    SchemaRelationship,
    StaticAnalysisResult,
)
from artifactor.intelligence.model import build_intelligence_model


def _make_validation() -> ValidationResult:
    return ValidationResult(
        validated_entities=[
            ValidatedEntity(
                name="greet",
                entity_type="function",
                file_path="main.py",
                line=1,
                source="ast",
                confidence=0.9,
            ),
            ValidatedEntity(
                name="helper",
                entity_type="function",
                file_path="main.py",
                line=10,
                source="cross_validated",
                confidence=0.95,
            ),
        ]
    )


def _make_static() -> StaticAnalysisResult:
    return StaticAnalysisResult(
        ast_forest=ASTForest(entities=[]),
        call_graph=CallGraph(
            edges=[
                CallEdge(
                    caller_file="main.py",
                    caller_line=5,
                    callee="helper",
                )
            ]
        ),
        dependency_graph=DependencyGraph(
            edges=[
                DependencyEdge(
                    source_file="main.py",
                    target="os",
                )
            ]
        ),
    )


def _make_llm() -> LLMAnalysisResult:
    return LLMAnalysisResult(
        narratives=[
            ModuleNarrative(
                file_path="main.py",
                purpose="Entry point for greeting users",
                confidence="high",
            )
        ],
        business_rules=[
            BusinessRule(
                rule_text="Greet by name only",
                rule_type="validation",
                confidence="medium",
            )
        ],
    )


def test_build_creates_model() -> None:
    model = build_intelligence_model(
        "proj-1",
        _make_validation(),
        _make_static(),
        _make_llm(),
    )
    assert model.project_id == "proj-1"
    assert model.created_at is not None


def test_entities_in_knowledge_graph() -> None:
    model = build_intelligence_model(
        "proj-1",
        _make_validation(),
        _make_static(),
        _make_llm(),
    )
    kg = model.knowledge_graph
    assert len(kg.entities) == 2
    greet = kg.get_entity("main.py::greet")
    assert greet is not None
    assert greet.entity_type == "function"


def test_call_edges_resolved_to_entity_ids() -> None:
    model = build_intelligence_model(
        "proj-1",
        _make_validation(),
        _make_static(),
        _make_llm(),
    )
    kg = model.knowledge_graph
    call_rels = [
        r
        for r in kg.relationships
        if r.relationship_type == "calls"
    ]
    assert len(call_rels) == 1
    # Source resolved to entity in main.py containing line 5
    assert call_rels[0].source_id == "main.py::greet"
    # Target resolved to entity named "helper"
    assert call_rels[0].target_id == "main.py::helper"


def test_dependency_edges_resolved_to_entity_ids() -> None:
    model = build_intelligence_model(
        "proj-1",
        _make_validation(),
        _make_static(),
        _make_llm(),
    )
    kg = model.knowledge_graph
    import_rels = [
        r
        for r in kg.relationships
        if r.relationship_type == "imports"
    ]
    assert len(import_rels) == 1
    # Source resolved to first entity in main.py
    assert import_rels[0].source_id == "main.py::greet"
    # Target stays as raw module name
    assert import_rels[0].target_id == "os"


def test_purposes_from_narratives() -> None:
    model = build_intelligence_model(
        "proj-1",
        _make_validation(),
        _make_static(),
        _make_llm(),
    )
    rg = model.reasoning_graph
    purpose = rg.get_purpose("main.py")
    assert purpose is not None
    assert "greeting" in purpose.statement.lower()


def test_rules_from_llm() -> None:
    model = build_intelligence_model(
        "proj-1",
        _make_validation(),
        _make_static(),
        _make_llm(),
    )
    rg = model.reasoning_graph
    assert len(rg.rules) == 1


def test_empty_inputs() -> None:
    model = build_intelligence_model(
        "proj-1",
        ValidationResult(),
        StaticAnalysisResult(ast_forest=ASTForest(entities=[])),
        LLMAnalysisResult(),
    )
    assert len(model.knowledge_graph.entities) == 0
    assert len(model.reasoning_graph.purposes) == 0


def test_api_endpoints_become_entities() -> None:
    static = StaticAnalysisResult(
        ast_forest=ASTForest(entities=[]),
        api_endpoints=APIEndpoints(
            endpoints=[
                APIEndpoint(
                    method="GET",
                    path="/api/users",
                    handler_file="routes.py",
                    handler_function="list_users",
                    handler_line=5,
                    parameters=[
                        APIParameter(
                            name="page", location="query"
                        )
                    ],
                    response_type="UserList",
                ),
                APIEndpoint(
                    method="POST",
                    path="/api/users",
                    handler_file="routes.py",
                    handler_function="create_user",
                    handler_line=20,
                ),
            ]
        ),
    )
    model = build_intelligence_model(
        "proj-1",
        ValidationResult(),
        static,
        LLMAnalysisResult(),
    )
    kg = model.knowledge_graph
    endpoints = kg.find_by_type("endpoint")
    assert len(endpoints) == 2
    get_ep = kg.get_entity("routes.py::GET_/api/users")
    assert get_ep is not None
    assert get_ep.name == "GET /api/users"
    assert "params: page" in (get_ep.description or "")
    assert "returns: UserList" in (get_ep.description or "")


def test_schema_entities_with_table_prefix() -> None:
    static = StaticAnalysisResult(
        ast_forest=ASTForest(entities=[]),
        schema_map=SchemaMap(
            entities=[
                SchemaEntity(
                    name="User",
                    source_type="orm_model",
                    file_path="models.py",
                    start_line=10,
                    attributes=[
                        SchemaAttribute(
                            name="id",
                            data_type="int",
                            primary_key=True,
                        ),
                        SchemaAttribute(
                            name="email",
                            data_type="str",
                        ),
                    ],
                )
            ]
        ),
    )
    model = build_intelligence_model(
        "proj-1",
        ValidationResult(),
        static,
        LLMAnalysisResult(),
    )
    kg = model.knowledge_graph
    tables = kg.find_by_type("table")
    assert len(tables) == 1
    # Uses table: prefix in ID
    user = kg.get_entity("models.py::table:User")
    assert user is not None
    assert user.name == "User"
    assert "id, email" in (user.description or "")


def test_schema_relationships_cross_file() -> None:
    """FK references resolve across files via name-to-id index."""
    static = StaticAnalysisResult(
        ast_forest=ASTForest(entities=[]),
        schema_map=SchemaMap(
            entities=[
                SchemaEntity(
                    name="User",
                    source_type="orm_model",
                    file_path="user.py",
                    start_line=1,
                ),
                SchemaEntity(
                    name="Order",
                    source_type="orm_model",
                    file_path="order.py",
                    start_line=1,
                    relationships=[
                        SchemaRelationship(
                            target_entity="User",
                            relationship_type="many_to_one",
                            foreign_key="user_id",
                        )
                    ],
                ),
            ]
        ),
    )
    model = build_intelligence_model(
        "proj-1",
        ValidationResult(),
        static,
        LLMAnalysisResult(),
    )
    kg = model.knowledge_graph
    refs = [
        r
        for r in kg.relationships
        if r.relationship_type == "references"
    ]
    assert len(refs) == 1
    # Target resolves to user.py, not order.py (cross-file)
    assert refs[0].target_id == "user.py::table:User"
    assert refs[0].source_id == "order.py::table:Order"


def test_class_and_table_coexist() -> None:
    """Class entity (step 1) and table entity (step 3b) coexist."""
    validation = ValidationResult(
        validated_entities=[
            ValidatedEntity(
                name="User",
                entity_type="class",
                file_path="models.py",
                line=10,
                source="ast",
                confidence=0.9,
            )
        ]
    )
    static = StaticAnalysisResult(
        ast_forest=ASTForest(entities=[]),
        schema_map=SchemaMap(
            entities=[
                SchemaEntity(
                    name="User",
                    source_type="orm_model",
                    file_path="models.py",
                    start_line=10,
                )
            ]
        ),
    )
    model = build_intelligence_model(
        "proj-1",
        validation,
        static,
        LLMAnalysisResult(),
    )
    kg = model.knowledge_graph
    # Both exist with different IDs
    class_entity = kg.get_entity("models.py::User")
    table_entity = kg.get_entity("models.py::table:User")
    assert class_entity is not None
    assert table_entity is not None
    assert class_entity.entity_type == "class"
    assert table_entity.entity_type == "table"


def test_risks_added_to_reasoning_graph() -> None:
    llm = LLMAnalysisResult(
        risks=[
            RiskIndicator(
                risk_type="security",
                severity="high",
                title="SQL injection risk",
                description="User input used in query",
                file_path="handler.py",
                line=42,
                recommendations=["Use parameterized queries"],
                confidence="high",
            )
        ]
    )
    model = build_intelligence_model(
        "proj-1",
        ValidationResult(),
        StaticAnalysisResult(
            ast_forest=ASTForest(entities=[])
        ),
        llm,
    )
    rg = model.reasoning_graph
    assert len(rg.risks) == 1
    risk = next(iter(rg.risks.values()))
    assert risk.title == "SQL injection risk"
    assert risk.severity == "high"
    assert risk.confidence.value == 0.9
    assert risk.recommendations == (
        "Use parameterized queries",
    )


def test_low_confidence_narratives_filtered() -> None:
    """Low-confidence narratives are excluded from reasoning graph."""
    llm = LLMAnalysisResult(
        narratives=[
            ModuleNarrative(
                file_path="good.py",
                purpose="Handles user authentication",
                confidence="high",
            ),
            ModuleNarrative(
                file_path="bad.py",
                purpose="Analysis unavailable",
                confidence="low",
            ),
        ]
    )
    model = build_intelligence_model(
        "proj-1",
        ValidationResult(),
        StaticAnalysisResult(
            ast_forest=ASTForest(entities=[])
        ),
        llm,
    )
    rg = model.reasoning_graph
    assert len(rg.purposes) == 1
    assert rg.get_purpose("good.py") is not None
    assert rg.get_purpose("bad.py") is None


def test_unresolvable_call_edge_dropped() -> None:
    """Call edges with no matching entities are silently dropped."""
    validation = ValidationResult(
        validated_entities=[
            ValidatedEntity(
                name="greet",
                entity_type="function",
                file_path="main.py",
                line=1,
                source="ast",
                confidence=0.9,
            ),
        ]
    )
    static = StaticAnalysisResult(
        ast_forest=ASTForest(entities=[]),
        call_graph=CallGraph(
            edges=[
                CallEdge(
                    caller_file="main.py",
                    caller_line=5,
                    callee="nonexistent_func",
                )
            ]
        ),
    )
    model = build_intelligence_model(
        "proj-1",
        validation,
        static,
        LLMAnalysisResult(),
    )
    kg = model.knowledge_graph
    call_rels = [
        r
        for r in kg.relationships
        if r.relationship_type == "calls"
    ]
    assert len(call_rels) == 0


def test_low_confidence_rules_filtered() -> None:
    """Low-confidence rules are excluded from reasoning graph."""
    llm = LLMAnalysisResult(
        business_rules=[
            BusinessRule(
                rule_text="Validate email format",
                rule_type="validation",
                confidence="high",
            ),
            BusinessRule(
                rule_text="Unknown rule",
                rule_type="validation",
                confidence="low",
            ),
        ]
    )
    model = build_intelligence_model(
        "proj-1",
        ValidationResult(),
        StaticAnalysisResult(
            ast_forest=ASTForest(entities=[])
        ),
        llm,
    )
    rg = model.reasoning_graph
    assert len(rg.rules) == 1
    rule = next(iter(rg.rules.values()))
    assert rule.rule_text == "Validate email format"


def test_scope_aware_same_file_preference() -> None:
    """Callee resolution prefers same-file match over cross-file."""
    validation = ValidationResult(
        validated_entities=[
            ValidatedEntity(
                name="caller",
                entity_type="function",
                file_path="a.py",
                line=1,
                source="ast",
                confidence=0.9,
            ),
            ValidatedEntity(
                name="get",
                entity_type="function",
                file_path="a.py",
                line=10,
                source="ast",
                confidence=0.9,
            ),
            ValidatedEntity(
                name="get",
                entity_type="function",
                file_path="b.py",
                line=1,
                source="ast",
                confidence=0.9,
            ),
        ]
    )
    static = StaticAnalysisResult(
        ast_forest=ASTForest(entities=[]),
        call_graph=CallGraph(
            edges=[
                CallEdge(
                    caller_file="a.py",
                    caller_line=5,
                    callee="get",
                )
            ]
        ),
    )
    model = build_intelligence_model(
        "proj-1",
        validation,
        static,
        LLMAnalysisResult(),
    )
    kg = model.knowledge_graph
    call_rels = [
        r
        for r in kg.relationships
        if r.relationship_type == "calls"
    ]
    assert len(call_rels) == 1
    # Should prefer a.py::get (same file) over b.py::get
    assert call_rels[0].target_id == "a.py::get"


def test_scope_aware_receiver_field() -> None:
    """CallEdge with receiver populates the field."""
    edge = CallEdge(
        caller_file="main.py",
        caller_line=5,
        callee="get",
        receiver="repo",
    )
    assert edge.receiver == "repo"
