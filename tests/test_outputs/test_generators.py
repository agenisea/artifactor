"""Tests for all 13 section generators (template fallback path)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
from artifactor.config import Settings
from artifactor.intelligence.model import (
    IntelligenceModel,
    build_intelligence_model,
)
from artifactor.outputs import SECTION_GENERATORS
from artifactor.outputs.base import SectionOutput


def _make_settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        litellm_model_chain=["model-a"],
        llm_timeout_seconds=30,
    )


def _make_model(
    *,
    entities: bool = True,
    rules: bool = True,
    calls: bool = True,
    imports: bool = True,
    narratives: bool = True,
) -> IntelligenceModel:
    """Build a test IntelligenceModel with optional data."""

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
            ValidatedEntity(
                name="User",
                entity_type="class",
                file_path="models.py",
                line=10,
                source="cross_validated",
                confidence=0.95,
            ),
            ValidatedEntity(
                name="login_handler",
                entity_type="function",
                file_path="auth.py",
                line=5,
                source="ast",
                confidence=0.9,
            ),
            ValidatedEntity(
                name="admin_dashboard",
                entity_type="function",
                file_path="views.py",
                line=20,
                source="llm",
                confidence=0.7,
            ),
            ValidatedEntity(
                name="api_endpoint",
                entity_type="endpoint",
                file_path="routes.py",
                line=1,
                source="ast",
                confidence=0.85,
            ),
        ]
        if entities
        else []
    )

    call_edges = (
        [
            CallEdge(
                caller_file="main.py",
                caller_line=5,
                callee="greet",
            )
        ]
        if calls
        else []
    )
    dep_edges = (
        [
            DependencyEdge(
                source_file="main.py",
                target="os",
            )
        ]
        if imports
        else []
    )
    static = StaticAnalysisResult(
        ast_forest=ASTForest(entities=[]),
        call_graph=CallGraph(edges=call_edges),
        dependency_graph=DependencyGraph(edges=dep_edges),
    )

    narr_list = (
        [
            ModuleNarrative(
                file_path="main.py",
                purpose="Entry point for greeting users",
                confidence="high",
            )
        ]
        if narratives
        else []
    )
    rule_list = (
        [
            BusinessRule(
                rule_text="Greet by name only",
                rule_type="validation",
                confidence="medium",
            )
        ]
        if rules
        else []
    )
    llm = LLMAnalysisResult(
        narratives=narr_list,
        business_rules=rule_list,
    )

    return build_intelligence_model(
        "test-project", validation, static, llm
    )


def _patch_synthesis_none():
    """Patch synthesize_section to return None across all generators."""
    return patch(
        "artifactor.outputs.synthesizer.guarded_llm_call",
        new_callable=AsyncMock,
        side_effect=RuntimeError("LLM unavailable"),
    )


class TestRegistry:
    def test_all_13_generators_registered(self) -> None:
        assert len(SECTION_GENERATORS) == 13

    def test_registry_keys_match_section_names(self) -> None:
        from artifactor.config import SECTION_TITLES

        for name in SECTION_TITLES:
            assert name in SECTION_GENERATORS


class TestExecutiveOverview:
    @pytest.mark.asyncio
    async def test_generates_content(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS[
                "executive_overview"
            ](model, "proj-1", settings)
        assert isinstance(out, SectionOutput)
        assert out.section_name == "executive_overview"
        assert "Executive Overview" in out.content

    @pytest.mark.asyncio
    async def test_empty_model(self) -> None:
        model = _make_model(
            entities=False,
            rules=False,
            calls=False,
            imports=False,
            narratives=False,
        )
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS[
                "executive_overview"
            ](model, "proj-1", settings)
        assert isinstance(out, SectionOutput)


class TestFeatures:
    @pytest.mark.asyncio
    async def test_generates_feature_table(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["features"](
                model, "proj-1", settings
            )
        assert "Features" in out.content
        assert "greet" in out.content


class TestPersonas:
    @pytest.mark.asyncio
    async def test_detects_admin_persona(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["personas"](
                model, "proj-1", settings
            )
        assert "Administrator" in out.content

    @pytest.mark.asyncio
    async def test_default_persona_on_empty(self) -> None:
        model = _make_model(entities=False)
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["personas"](
                model, "proj-1", settings
            )
        assert "General User" in out.content


class TestUserStories:
    @pytest.mark.asyncio
    async def test_generates_stories_from_rules(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["user_stories"](
                model, "proj-1", settings
            )
        assert "As a" in out.content
        assert "greet by name only" in out.content.lower()

    @pytest.mark.asyncio
    async def test_empty_rules(self) -> None:
        model = _make_model(rules=False)
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["user_stories"](
                model, "proj-1", settings
            )
        assert isinstance(out, SectionOutput)


class TestSecurityRequirements:
    @pytest.mark.asyncio
    async def test_detects_auth_entities(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS[
                "security_requirements"
            ](model, "proj-1", settings)
        assert "login_handler" in out.content

    @pytest.mark.asyncio
    async def test_empty_no_auth(self) -> None:
        model = _make_model(entities=False)
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS[
                "security_requirements"
            ](model, "proj-1", settings)
        assert "No authentication" in out.content


class TestSystemOverview:
    @pytest.mark.asyncio
    async def test_generates_mermaid_diagram(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS[
                "system_overview"
            ](model, "proj-1", settings)
        assert "System Overview" in out.content

    @pytest.mark.asyncio
    async def test_module_tree(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS[
                "system_overview"
            ](model, "proj-1", settings)
        assert "Module Tree" in out.content


class TestDataModels:
    @pytest.mark.asyncio
    async def test_finds_class_entities(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["data_models"](
                model, "proj-1", settings
            )
        assert "User" in out.content

    @pytest.mark.asyncio
    async def test_empty_no_classes(self) -> None:
        model = _make_model(entities=False)
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["data_models"](
                model, "proj-1", settings
            )
        assert "No data model entities" in out.content


class TestInterfaces:
    @pytest.mark.asyncio
    async def test_generates_content(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["interfaces"](
                model, "proj-1", settings
            )
        assert "Interface" in out.content


class TestUISpecs:
    @pytest.mark.asyncio
    async def test_no_ui_entities(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["ui_specs"](
                model, "proj-1", settings
            )
        assert "No UI components" in out.content


class TestAPISpecs:
    @pytest.mark.asyncio
    async def test_finds_endpoints(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["api_specs"](
                model, "proj-1", settings
            )
        assert "api_endpoint" in out.content


class TestIntegrations:
    @pytest.mark.asyncio
    async def test_finds_imports(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["integrations"](
                model, "proj-1", settings
            )
        assert "Integration" in out.content


class TestTechStories:
    @pytest.mark.asyncio
    async def test_generates_tech_stories(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS["tech_stories"](
                model, "proj-1", settings
            )
        assert "Technical" in out.content


class TestSecurityConsiderations:
    @pytest.mark.asyncio
    async def test_coverage_summary(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS[
                "security_considerations"
            ](model, "proj-1", settings)
        assert "Coverage Summary" in out.content

    @pytest.mark.asyncio
    async def test_detects_login_as_auth(self) -> None:
        model = _make_model()
        settings = _make_settings()
        with _patch_synthesis_none():
            out = await SECTION_GENERATORS[
                "security_considerations"
            ](model, "proj-1", settings)
        assert "Authentication entities: Found" in out.content
