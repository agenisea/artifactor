"""Tests for LLM section synthesis."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from artifactor.analysis.llm._llm_call import LLMCallResult
from artifactor.config import Settings
from artifactor.constants import Confidence
from artifactor.outputs.synthesizer import (
    SynthesisResult,
    _strip_fences,
    synthesize_section,
)


def _make_settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        litellm_model_chain=["model-a", "model-b"],
        llm_timeout_seconds=30,
    )


def _make_llm_result(content: str = "# Hello\nWorld") -> LLMCallResult:
    return LLMCallResult(
        content=content,
        model="model-a",
        input_tokens=100,
        output_tokens=50,
        cached_tokens=0,
    )


class TestStripFences:
    def test_removes_markdown_fences(self) -> None:
        text = "```markdown\n# Title\nContent\n```"
        assert _strip_fences(text) == "# Title\nContent"

    def test_removes_md_fences(self) -> None:
        text = "```md\n# Title\nContent\n```"
        assert _strip_fences(text) == "# Title\nContent"

    def test_no_fences_passthrough(self) -> None:
        text = "# Title\nContent"
        assert _strip_fences(text) == "# Title\nContent"

    def test_bare_fences(self) -> None:
        text = "```\n# Title\nContent\n```"
        assert _strip_fences(text) == "# Title\nContent"


class TestSynthesizeSection:
    @pytest.mark.asyncio
    async def test_successful_synthesis(self) -> None:
        settings = _make_settings()
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            return_value=_make_llm_result("# Overview\nGreat project."),
        ):
            result = await synthesize_section(
                "executive_overview",
                "You are a writer.",
                "<context>{}</context>",
                settings,
            )

        assert result is not None
        assert isinstance(result, SynthesisResult)
        assert "Great project" in result.content
        assert result.confidence == Confidence.LLM_SECTION_RICH
        assert result.model_used == "model-a"
        assert result.input_tokens == 100
        assert result.output_tokens == 50

    @pytest.mark.asyncio
    async def test_model_chain_fallback(self) -> None:
        """First model raises, second succeeds."""
        settings = _make_settings()
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            side_effect=[
                RuntimeError("model-a down"),
                _make_llm_result("# Fallback\nContent"),
            ],
        ):
            result = await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert result is not None
        assert "Fallback" in result.content

    @pytest.mark.asyncio
    async def test_all_models_fail_returns_none(self) -> None:
        settings = _make_settings()
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            side_effect=RuntimeError("all down"),
        ):
            result = await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_circuit_breaker_caught(self) -> None:
        from circuitbreaker import CircuitBreakerError

        settings = _make_settings()
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            side_effect=CircuitBreakerError(None),
        ):
            result = await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_strip_markdown_fences_in_output(self) -> None:
        settings = _make_settings()
        fenced = "```markdown\n# Title\nBody\n```"
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            return_value=_make_llm_result(fenced),
        ):
            result = await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert result is not None
        assert result.content == "# Title\nBody"

    @pytest.mark.asyncio
    async def test_empty_content_tries_next_model(self) -> None:
        settings = _make_settings()
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            side_effect=[
                _make_llm_result(""),
                _make_llm_result("# Real Content"),
            ],
        ):
            result = await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert result is not None
        assert "Real Content" in result.content
