"""Tests for LLM synthesis path in section generators."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from artifactor.analysis.llm.schemas import (
    LLMAnalysisResult,
    ModuleNarrative,
)
from artifactor.analysis.quality.schemas import (
    ValidatedEntity,
    ValidationResult,
)
from artifactor.analysis.static.schemas import (
    ASTForest,
    CallGraph,
    DependencyGraph,
    StaticAnalysisResult,
)
from artifactor.config import Settings
from artifactor.constants import Confidence
from artifactor.intelligence.model import (
    IntelligenceModel,
    build_intelligence_model,
)
from artifactor.outputs.base import SectionOutput
from artifactor.outputs.synthesizer import SynthesisResult


def _make_settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        litellm_model_chain=["model-a"],
        llm_timeout_seconds=30,
    )


def _make_model() -> IntelligenceModel:
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
        call_graph=CallGraph(edges=[]),
        dependency_graph=DependencyGraph(edges=[]),
    )
    llm = LLMAnalysisResult(
        narratives=[
            ModuleNarrative(
                file_path="main.py",
                purpose="Main entry",
                confidence="high",
            ),
        ],
        business_rules=[],
    )
    return build_intelligence_model(
        "test-project", validation, static, llm
    )


def _make_synthesis_result(
    content: str = "# Section\nGenerated content.",
) -> SynthesisResult:
    return SynthesisResult(
        content=content,
        confidence=Confidence.LLM_SECTION_RICH,
        model_used="model-a",
        input_tokens=100,
        output_tokens=50,
    )


class TestLLMPathUsed:
    @pytest.mark.asyncio
    async def test_llm_path_used_when_available(self) -> None:
        """When synthesize_section returns content, generator uses it."""
        from artifactor.outputs.executive_overview import (
            generate,
        )

        model = _make_model()
        settings = _make_settings()

        with patch(
            "artifactor.outputs.base"
            ".synthesize_section",
            new_callable=AsyncMock,
            return_value=_make_synthesis_result(
                "# Executive Overview\nA great project."
            ),
        ):
            out = await generate(model, "proj-1", settings)

        assert isinstance(out, SectionOutput)
        assert "A great project" in out.content
        # Generator sets confidence based on context item count
        assert out.confidence in (
            Confidence.LLM_SECTION_SPARSE,
            Confidence.LLM_SECTION_RICH,
        )

    @pytest.mark.asyncio
    async def test_template_fallback_on_synthesis_failure(
        self,
    ) -> None:
        """When synthesize_section returns None, template is used."""
        from artifactor.outputs.executive_overview import (
            generate,
        )

        model = _make_model()
        settings = _make_settings()

        with patch(
            "artifactor.outputs.base"
            ".synthesize_section",
            new_callable=AsyncMock,
            return_value=None,
        ):
            out = await generate(model, "proj-1", settings)

        assert isinstance(out, SectionOutput)
        assert "Executive Overview" in out.content
        # Template output has lower confidence from avg_confidence
        assert out.confidence != 0.85

    @pytest.mark.asyncio
    async def test_llm_output_has_correct_section_name(
        self,
    ) -> None:
        """LLM-generated output preserves section_name."""
        from artifactor.outputs.features import generate

        model = _make_model()
        settings = _make_settings()

        with patch(
            "artifactor.outputs.base.synthesize_section",
            new_callable=AsyncMock,
            return_value=_make_synthesis_result(
                "# Features\nCool features."
            ),
        ):
            out = await generate(model, "proj-1", settings)

        assert out.section_name == "features"
        assert "Cool features" in out.content
