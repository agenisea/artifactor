"""Tests for circuit breaker protection on external services."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from circuitbreaker import CircuitBreakerError, CircuitBreakerMonitor
from tenacity import wait_none

from artifactor.analysis.llm._llm_call import (
    _breaker_registry,
    guarded_llm_call,
)
from artifactor.analysis.llm.combined import analyze_chunk
from artifactor.analysis.llm.embedder import _guarded_embed
from artifactor.config import Settings
from artifactor.ingestion.schemas import CodeChunk


@pytest.fixture(autouse=True)
def _reset_breakers() -> None:
    """Reset circuit breakers between tests."""
    _breaker_registry.clear()
    for cb in CircuitBreakerMonitor.get_circuits():
        cb.reset()  # type: ignore[union-attr]


@pytest.fixture(autouse=True)
def _disable_retry_wait() -> Any:
    """Disable tenacity wait time for fast tests."""
    original_wait = guarded_llm_call.retry.wait  # type: ignore[union-attr]
    guarded_llm_call.retry.wait = wait_none()  # type: ignore[union-attr]
    yield
    guarded_llm_call.retry.wait = original_wait  # type: ignore[union-attr]


def _make_chunk() -> CodeChunk:
    return CodeChunk(
        file_path="test.py",
        content="def hello(): pass",
        language="python",
        chunk_type="function",
        start_line=1,
        end_line=1,
    )


class TestLLMCircuitBreaker:
    async def test_circuit_opens_after_threshold(
        self,
    ) -> None:
        """After 5 failures, circuit opens and raises CircuitBreakerError.

        tenacity retries 3x per call, so each guarded_llm_call attempt
        triggers 3 _acompletion calls before reraising ConnectionError.
        After 5 ConnectionErrors hit the breaker, the 6th call opens it.
        """
        with patch(
            "artifactor.analysis.llm._llm_call._acompletion",
            new_callable=AsyncMock,
            side_effect=ConnectionError("API down"),
        ):
            # First 5 calls raise ConnectionError (tracked by breaker)
            # Each call has 3 tenacity retries, all fail with ConnectionError
            for _ in range(5):
                with pytest.raises(ConnectionError):
                    await guarded_llm_call(
                        "test-model",
                        [{"role": "user", "content": "hi"}],
                        10,
                    )

            # 6th call should raise CircuitBreakerError (circuit open)
            with pytest.raises(CircuitBreakerError):
                await guarded_llm_call(
                    "test-model",
                    [{"role": "user", "content": "hi"}],
                    10,
                )

    async def test_combined_returns_low_confidence_on_circuit_open(
        self,
    ) -> None:
        """When circuit opens, analyze_chunk returns graceful degradation."""
        chunk = _make_chunk()
        settings = Settings()

        # Open breakers for both models
        with patch(
            "artifactor.analysis.llm._llm_call._acompletion",
            new_callable=AsyncMock,
            side_effect=ConnectionError("API down"),
        ):
            for model in settings.litellm_model_chain:
                for _ in range(5):
                    with pytest.raises(ConnectionError):
                        await guarded_llm_call(
                            model,
                            [{"role": "user", "content": "hi"}],
                            10,
                        )

            # Now analyze_chunk should detect open circuit on both models
            narrative, rules, risks = await analyze_chunk(
                chunk, "python", settings
            )
            assert narrative.confidence == "low"
            assert narrative.purpose == "Analysis unavailable"
            assert rules == []
            assert risks == []


class TestEmbeddingCircuitBreaker:
    async def test_embedding_circuit_opens_after_threshold(
        self,
    ) -> None:
        """Embedding circuit opens after 3 failures."""
        with patch(
            "artifactor.analysis.llm.embedder._aembedding",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Embed API down"),
        ):
            for _ in range(3):
                with pytest.raises(ConnectionError):
                    await _guarded_embed(
                        "text-embedding-3-small", ["test"]
                    )

            with pytest.raises(CircuitBreakerError):
                await _guarded_embed(
                    "text-embedding-3-small", ["test"]
                )

    async def test_embedding_circuit_independent_from_llm(
        self,
    ) -> None:
        """Embedding and LLM breakers are independent."""
        # Open the LLM circuit for a specific model
        with patch(
            "artifactor.analysis.llm._llm_call._acompletion",
            new_callable=AsyncMock,
            side_effect=ConnectionError("LLM down"),
        ):
            for _ in range(5):
                with pytest.raises(ConnectionError):
                    await guarded_llm_call(
                        "test-model",
                        [{"role": "user", "content": "hi"}],
                        10,
                    )

        # LLM circuit is open
        with pytest.raises(CircuitBreakerError):
            await guarded_llm_call(
                "test-model",
                [{"role": "user", "content": "hi"}],
                10,
            )

        # But embedding circuit should still be closed
        mock_response = AsyncMock()
        mock_response.data = [{"embedding": [0.1, 0.2]}]
        with patch(
            "artifactor.analysis.llm.embedder._aembedding",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await _guarded_embed(
                "text-embedding-3-small", ["test"]
            )
            assert result.data[0]["embedding"] == [0.1, 0.2]
