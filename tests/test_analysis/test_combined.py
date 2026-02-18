"""Tests for the combined LLM analysis module."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from circuitbreaker import CircuitBreakerMonitor
from litellm.exceptions import RateLimitError as LitellmRateLimitError
from tenacity import wait_none

from artifactor.analysis.llm._llm_call import (
    _breaker_registry,
    guarded_llm_call,
)
from artifactor.analysis.llm.combined import (
    _extract_narrative,
    _extract_risks,
    _extract_rules,
    _normalize_entries,
    _parse_combined,
    analyze_chunk,
)
from artifactor.config import Settings
from artifactor.ingestion.schemas import CodeChunk


@pytest.fixture(autouse=True)
def _reset_breakers() -> None:
    """Reset circuit breakers between tests."""
    _breaker_registry.clear()
    for cb in CircuitBreakerMonitor.get_circuits():
        cb.reset()  # type: ignore[union-attr]


def _make_chunk() -> CodeChunk:
    return CodeChunk(
        file_path=Path("src/main.py"),
        language="python",
        chunk_type="function",
        start_line=1,
        end_line=10,
        content="def greet(name):\n    return f'Hello {name}'",
    )


def _mock_response(content: str) -> Any:
    """Build a mock litellm response with usage metadata."""
    msg = type("Msg", (), {"content": content})()
    choice = type("Choice", (), {"message": msg})()
    usage = type(
        "Usage",
        (),
        {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_tokens_details": None,
        },
    )()
    return type(
        "Response", (), {"choices": [choice], "usage": usage}
    )()


def _combined_json(
    purpose: str = "Greet a user",
    confidence: str = "high",
    rules: list[dict[str, Any]] | None = None,
    risks: list[dict[str, Any]] | None = None,
) -> str:
    """Build a valid combined analysis JSON response."""
    return json.dumps({
        "purpose": purpose,
        "confidence": confidence,
        "behaviors": [{"description": "Says hello"}],
        "domain_concepts": [{"concept": "Greeting"}],
        "rules": rules or [],
        "risks": risks or [],
    })


class TestParseCombined:
    def test_valid_json_all_sections(self) -> None:
        raw = _combined_json(
            rules=[{
                "rule_text": "Name must be non-empty",
                "rule_type": "validation",
                "condition": "name is empty",
                "consequence": "raises ValueError",
                "confidence": "high",
                "affected_entities": ["User"],
                "citations": ["main.py:1-2"],
            }],
            risks=[{
                "risk_type": "error_handling",
                "severity": "medium",
                "title": "No input validation",
                "description": "No check for empty name",
                "file_path": "main.py",
                "line": 1,
                "recommendations": ["Add validation"],
                "confidence": "medium",
            }],
        )
        narrative, rules, risks = _parse_combined(
            raw, "src/main.py"
        )
        assert narrative.purpose == "Greet a user"
        assert narrative.confidence == "high"
        assert len(narrative.behaviors) == 1
        assert len(rules) == 1
        assert rules[0].rule_text == "Name must be non-empty"
        assert len(risks) == 1
        assert risks[0].title == "No input validation"

    def test_invalid_json_returns_empty_defaults(self) -> None:
        narrative, rules, risks = _parse_combined(
            "not json", "src/main.py"
        )
        assert narrative.confidence == "low"
        assert "Failed to parse" in narrative.purpose
        assert rules == []
        assert risks == []

    def test_empty_object_returns_defaults(self) -> None:
        narrative, rules, risks = _parse_combined(
            "{}", "src/main.py"
        )
        assert narrative.purpose == ""
        assert narrative.confidence == "medium"
        assert rules == []
        assert risks == []

    def test_missing_rules_and_risks(self) -> None:
        raw = json.dumps({
            "purpose": "A utility function",
            "confidence": "high",
        })
        narrative, rules, risks = _parse_combined(
            raw, "src/main.py"
        )
        assert narrative.purpose == "A utility function"
        assert rules == []
        assert risks == []


class TestExtractNarrative:
    def test_extracts_all_fields(self) -> None:
        data: dict[str, Any] = {
            "purpose": "Test purpose",
            "confidence": "high",
            "behaviors": [{"description": "Does stuff"}],
            "domain_concepts": [{"concept": "Thing"}],
        }
        result = _extract_narrative(data, "test.py")
        assert result.purpose == "Test purpose"
        assert result.confidence == "high"
        assert len(result.behaviors) == 1
        assert len(result.domain_concepts) == 1


class TestExtractRules:
    def test_extracts_rules(self) -> None:
        data: dict[str, Any] = {
            "rules": [{
                "rule_text": "Users must be 18+",
                "rule_type": "validation",
                "confidence": "high",
            }]
        }
        rules = _extract_rules(data)
        assert len(rules) == 1
        assert rules[0].rule_text == "Users must be 18+"

    def test_non_list_returns_empty(self) -> None:
        assert _extract_rules({"rules": "not a list"}) == []

    def test_skips_invalid_entries(self) -> None:
        data: dict[str, Any] = {
            "rules": [
                "not a dict",
                {"rule_text": "Valid rule"},
            ]
        }
        rules = _extract_rules(data)
        assert len(rules) == 1


class TestExtractRisks:
    def test_extracts_risks(self) -> None:
        data: dict[str, Any] = {
            "risks": [{
                "risk_type": "security",
                "severity": "high",
                "title": "SQL injection",
            }]
        }
        risks = _extract_risks(data)
        assert len(risks) == 1
        assert risks[0].risk_type == "security"

    def test_non_list_returns_empty(self) -> None:
        assert _extract_risks({"risks": "not a list"}) == []


class TestNormalizeEntries:
    def test_list_citations_joined(self) -> None:
        raw = [{"name": "foo", "citations": ["a.py:1", "b.py:2"]}]
        result = _normalize_entries(raw)
        assert result == [
            {"name": "foo", "citations": "a.py:1, b.py:2"}
        ]

    def test_non_list_returns_empty(self) -> None:
        assert _normalize_entries("not a list") == []


class TestAnalyzeChunk:
    @pytest.mark.asyncio
    async def test_successful_combined_analysis(self) -> None:
        response = _mock_response(_combined_json(
            rules=[{
                "rule_text": "Test rule",
                "rule_type": "validation",
            }],
        ))
        with patch(
            "artifactor.analysis.llm._llm_call._acompletion",
            new=AsyncMock(return_value=response),
        ):
            narrative, rules, risks = await analyze_chunk(
                _make_chunk(), "python", Settings()
            )
        assert narrative.purpose == "Greet a user"
        assert narrative.confidence == "high"
        assert len(rules) == 1
        assert rules[0].rule_text == "Test rule"
        assert risks == []

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self) -> None:
        response = _mock_response(_combined_json())
        mock = AsyncMock(
            side_effect=[Exception("primary failed"), response]
        )
        with patch(
            "artifactor.analysis.llm._llm_call._acompletion",
            new=mock,
        ):
            narrative, rules, risks = await analyze_chunk(
                _make_chunk(), "python", Settings()
            )
        assert narrative.purpose == "Greet a user"
        assert mock.call_count == 2

    @pytest.mark.asyncio
    async def test_all_models_fail_returns_unavailable(self) -> None:
        mock = AsyncMock(side_effect=Exception("all failed"))
        with patch(
            "artifactor.analysis.llm._llm_call._acompletion",
            new=mock,
        ):
            narrative, rules, risks = await analyze_chunk(
                _make_chunk(), "python", Settings()
            )
        assert narrative.confidence == "low"
        assert "unavailable" in narrative.purpose.lower()
        assert rules == []
        assert risks == []

    @pytest.mark.asyncio
    async def test_malformed_json_returns_defaults(self) -> None:
        response = _mock_response("not valid json at all")
        with patch(
            "artifactor.analysis.llm._llm_call._acompletion",
            new=AsyncMock(return_value=response),
        ):
            narrative, rules, risks = await analyze_chunk(
                _make_chunk(), "python", Settings()
            )
        assert narrative.confidence == "low"
        assert "Failed to parse" in narrative.purpose
        assert rules == []
        assert risks == []


class TestRateLimitHandling:
    """Tests for rate-limit retry and circuit breaker exclusion."""

    @pytest.fixture(autouse=True)
    def _disable_retry_wait(self) -> Any:
        """Disable tenacity wait time for fast tests."""
        original_wait = guarded_llm_call.retry.wait  # type: ignore[union-attr]
        guarded_llm_call.retry.wait = wait_none()  # type: ignore[union-attr]
        yield
        guarded_llm_call.retry.wait = original_wait  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_then_succeeds(self) -> None:
        """guarded_llm_call retries RateLimitError, succeeds on 3rd."""
        response = _mock_response(_combined_json())
        rate_err = LitellmRateLimitError(
            message="Rate limit exceeded",
            model="test",
            llm_provider="openai",
        )
        mock = AsyncMock(
            side_effect=[rate_err, rate_err, response]
        )
        with patch(
            "artifactor.analysis.llm._llm_call._acompletion",
            new=mock,
        ):
            narrative, rules, risks = await analyze_chunk(
                _make_chunk(), "python", Settings()
            )
        assert narrative.purpose == "Greet a user"
        # 2 retries + 1 success = 3 _acompletion calls
        assert mock.call_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_excludes_rate_limit(self) -> None:
        """RateLimitErrors don't count toward circuit breaker failures.

        With failure_threshold=5, 18+ consecutive RateLimitErrors should
        NOT open the circuit. If CB were counting them, it would open
        after 5 and subsequent calls would raise CircuitBreakerError.
        """
        rate_err = LitellmRateLimitError(
            message="Rate limit exceeded",
            model="test",
            llm_provider="openai",
        )
        mock = AsyncMock(side_effect=rate_err)
        with patch(
            "artifactor.analysis.llm._llm_call._acompletion",
            new=mock,
        ):
            # Each analyze_chunk: 2 models × 3 retries = 6 calls
            # 3 iterations × 6 = 18 calls, all RateLimitError
            for _ in range(3):
                narrative, _, _ = await analyze_chunk(
                    _make_chunk(), "python", Settings()
                )
                assert "unavailable" in narrative.purpose.lower()

        # If CB had opened, mock would have fewer calls
        # (CircuitBreakerError bypasses _acompletion)
        assert mock.call_count == 18
