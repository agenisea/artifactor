"""Tests for LLM section synthesis."""

from __future__ import annotations

import logging
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

# Content strings >= SECTION_MIN_LENGTH (50 chars)
_VALID_CONTENT = (
    "# Overview\n\n"
    "This is a comprehensive project overview section "
    "with enough detail to pass validation."
)
_VALID_FALLBACK = (
    "# Fallback\n\n"
    "This fallback content from the second model is "
    "long enough to pass the validation threshold."
)
_VALID_FENCED = (
    "```markdown\n"
    "# Title\n\n"
    "This is the fenced body content that should be "
    "unwrapped and still pass minimum length checks.\n"
    "```"
)
_VALID_FENCED_STRIPPED = (
    "# Title\n\n"
    "This is the fenced body content that should be "
    "unwrapped and still pass minimum length checks."
)
_SHORT_CONTENT = "Too short"


def _make_settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        litellm_model_chain=["model-a", "model-b"],
        llm_timeout_seconds=30,
    )


def _make_llm_result(
    content: str = _VALID_CONTENT,
) -> LLMCallResult:
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
            return_value=_make_llm_result(_VALID_CONTENT),
        ):
            result = await synthesize_section(
                "executive_overview",
                "You are a writer.",
                "<context>{}</context>",
                settings,
            )

        assert result is not None
        assert isinstance(result, SynthesisResult)
        assert "project overview" in result.content
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
                _make_llm_result(_VALID_FALLBACK),
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
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            return_value=_make_llm_result(_VALID_FENCED),
        ):
            result = await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert result is not None
        assert result.content == _VALID_FENCED_STRIPPED

    @pytest.mark.asyncio
    async def test_empty_content_tries_next_model(self) -> None:
        settings = _make_settings()
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            side_effect=[
                _make_llm_result(""),
                _make_llm_result(_VALID_CONTENT),
            ],
        ):
            result = await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert result is not None
        assert "project overview" in result.content

    # ── PLAN70: Validation tests ─────────────────────────

    @pytest.mark.asyncio
    async def test_validation_failure_falls_through(
        self,
    ) -> None:
        """Short content on model-a triggers validation failure,
        model-b returns valid content."""
        settings = _make_settings()
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            side_effect=[
                _make_llm_result(_SHORT_CONTENT),
                _make_llm_result(_VALID_CONTENT),
            ],
        ):
            result = await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert result is not None
        assert "project overview" in result.content

    @pytest.mark.asyncio
    async def test_validation_failure_all_models_returns_none(
        self,
    ) -> None:
        """All models return short content → None."""
        settings = _make_settings()
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            return_value=_make_llm_result(_SHORT_CONTENT),
        ):
            result = await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_valid_content_passes_unchanged(
        self,
    ) -> None:
        """Content above min_length passes through with
        whitespace stripped."""
        settings = _make_settings()
        padded = "  " + _VALID_CONTENT + "  \n"
        with patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            return_value=_make_llm_result(padded),
        ):
            result = await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert result is not None
        assert result.content == _VALID_CONTENT.strip()

    @pytest.mark.asyncio
    async def test_validation_failure_logs_event(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Validation failure emits structured log."""
        settings = _make_settings()
        with caplog.at_level(
            logging.WARNING
        ), patch(
            "artifactor.outputs.synthesizer.guarded_llm_call",
            new_callable=AsyncMock,
            return_value=_make_llm_result(_SHORT_CONTENT),
        ):
            await synthesize_section(
                "features", "prompt", "ctx", settings,
            )

        assert any(
            "synthesis_validation_failed" in r.message
            for r in caplog.records
        )
