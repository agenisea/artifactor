"""Tests for section prompts and context builders."""

from __future__ import annotations

import json

import pytest

from artifactor.analysis.llm.schemas import (
    BusinessRule,
    LLMAnalysisResult,
    ModuleNarrative,
)
from artifactor.analysis.quality.schemas import (
    ValidatedEntity,
    ValidationResult,
)
from artifactor.analysis.static.schemas import (
    ASTForest,
    CallEdge,
    CallGraph,
    DependencyEdge,
    DependencyGraph,
    StaticAnalysisResult,
)
from artifactor.config import SECTION_TITLES
from artifactor.intelligence.model import (
    IntelligenceModel,
    build_intelligence_model,
)
from artifactor.outputs.section_prompts import (
    CONTEXT_BUILDERS,
    MAX_ENTITIES,
    SECTION_SYSTEM_PROMPTS,
)


def _make_model(
    *,
    entity_count: int = 5,
) -> IntelligenceModel:
    """Build a test IntelligenceModel with controllable entity count."""
    entities = [
        ValidatedEntity(
            name=f"entity_{i}",
            entity_type="function" if i % 2 == 0 else "class",
            file_path=f"file_{i}.py",
            line=i,
            source="ast",
            confidence=0.9,
        )
        for i in range(entity_count)
    ]

    validation = ValidationResult(validated_entities=entities)

    static = StaticAnalysisResult(
        ast_forest=ASTForest(entities=[]),
        call_graph=CallGraph(
            edges=[
                CallEdge(
                    caller_file="file_0.py",
                    caller_line=1,
                    callee="entity_2",
                ),
            ]
        ),
        dependency_graph=DependencyGraph(
            edges=[
                DependencyEdge(
                    source_file="file_0.py",
                    target="os",
                ),
            ]
        ),
    )

    llm = LLMAnalysisResult(
        narratives=[
            ModuleNarrative(
                file_path="file_0.py",
                purpose="Main entry point",
                confidence="high",
            ),
        ],
        business_rules=[
            BusinessRule(
                rule_text="Must validate input",
                rule_type="validation",
                confidence="high",
            ),
        ],
    )

    return build_intelligence_model(
        "test-project", validation, static, llm
    )


def _empty_model() -> IntelligenceModel:
    """IntelligenceModel with no data."""
    validation = ValidationResult(validated_entities=[])
    static = StaticAnalysisResult(
        ast_forest=ASTForest(entities=[]),
        call_graph=CallGraph(edges=[]),
        dependency_graph=DependencyGraph(edges=[]),
    )
    llm = LLMAnalysisResult(narratives=[], business_rules=[])
    return build_intelligence_model(
        "test-project", validation, static, llm
    )


def _extract_json(context_str: str) -> dict:
    """Extract JSON from <context>...</context> wrapper."""
    start = context_str.index("<context>\n") + len("<context>\n")
    end = context_str.index("\n</context>")
    return json.loads(context_str[start:end])


class TestRegistryCompleteness:
    def test_all_sections_have_system_prompt(self) -> None:
        for name in SECTION_TITLES:
            assert name in SECTION_SYSTEM_PROMPTS, (
                f"Missing system prompt for {name}"
            )

    def test_all_sections_have_context_builder(self) -> None:
        for name in SECTION_TITLES:
            assert name in CONTEXT_BUILDERS, (
                f"Missing context builder for {name}"
            )


class TestContextBuilderOutput:
    @pytest.mark.parametrize(
        "section_name", list(CONTEXT_BUILDERS.keys())
    )
    def test_produces_valid_json(
        self, section_name: str
    ) -> None:
        model = _make_model()
        builder = CONTEXT_BUILDERS[section_name]
        result = builder(model)

        assert "<context>" in result
        assert "</context>" in result
        data = _extract_json(result)
        assert isinstance(data, dict)

    @pytest.mark.parametrize(
        "section_name", list(CONTEXT_BUILDERS.keys())
    )
    def test_empty_model_produces_valid_context(
        self, section_name: str
    ) -> None:
        model = _empty_model()
        builder = CONTEXT_BUILDERS[section_name]
        result = builder(model)

        data = _extract_json(result)
        assert isinstance(data, dict)

    def test_context_builder_caps_entities(self) -> None:
        model = _make_model(entity_count=50)
        result = CONTEXT_BUILDERS["executive_overview"](model)
        data = _extract_json(result)
        purposes = data.get("purposes", [])
        assert len(purposes) <= 15

    def test_executive_overview_has_stats(self) -> None:
        model = _make_model()
        result = CONTEXT_BUILDERS["executive_overview"](model)
        data = _extract_json(result)
        assert "stats" in data
        assert "purposes" in data
        assert "sample_rules" in data

    def test_features_has_functions(self) -> None:
        model = _make_model()
        result = CONTEXT_BUILDERS["features"](model)
        data = _extract_json(result)
        assert "function_entities" in data
        assert "file_purposes" in data

    def test_security_considerations_has_risks(self) -> None:
        model = _make_model()
        result = CONTEXT_BUILDERS[
            "security_considerations"
        ](model)
        data = _extract_json(result)
        assert "vulnerability_entities" in data
        assert "sensitive_entities" in data
        assert "risks" in data

    def test_entities_respect_max_cap(self) -> None:
        model = _make_model(entity_count=50)
        result = CONTEXT_BUILDERS["personas"](model)
        data = _extract_json(result)
        assert len(data["entities"]) <= MAX_ENTITIES
