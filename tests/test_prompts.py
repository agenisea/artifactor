"""Tests for consolidated LLM prompts module."""

from artifactor.prompts import (
    CHAT_AGENT_PROMPT,
    COMBINED_ANALYSIS_PROMPT,
    LANGUAGE_CONTEXT_MAP,
    build_analysis_prompt,
)


def test_language_context_map_has_six_languages() -> None:
    assert len(LANGUAGE_CONTEXT_MAP) == 6
    for lang in (
        "python", "java", "javascript", "typescript", "go", "rust"
    ):
        assert lang in LANGUAGE_CONTEXT_MAP


def test_build_analysis_prompt_structure() -> None:
    result = build_analysis_prompt("x = 1", "main.py", "python")
    assert "<code_chunk>" in result
    assert "</code_chunk>" in result
    assert "x = 1" in result
    assert "main.py" in result
    assert "python" in result


def test_build_analysis_prompt_injects_language_context() -> None:
    result = build_analysis_prompt("x = 1", "main.py", "python")
    assert "FastAPI" in result or "Pydantic" in result


def test_build_analysis_prompt_fallback_for_unknown_language() -> None:
    result = build_analysis_prompt("x = 1", "main.rb", "ruby")
    assert "Analyze based on observed patterns" in result


def test_combined_analysis_prompt_nonempty() -> None:
    assert len(COMBINED_ANALYSIS_PROMPT) > 200


def test_combined_analysis_prompt_requests_json() -> None:
    assert "JSON" in COMBINED_ANALYSIS_PROMPT


def test_combined_analysis_prompt_has_jtbd() -> None:
    assert "Job To Be Done" in COMBINED_ANALYSIS_PROMPT


def test_combined_analysis_prompt_has_example() -> None:
    assert "Expected output:" in COMBINED_ANALYSIS_PROMPT
    assert "create_user" in COMBINED_ANALYSIS_PROMPT


def test_combined_analysis_prompt_has_guardrails() -> None:
    assert "ALWAYS" in COMBINED_ANALYSIS_PROMPT
    assert "NEVER" in COMBINED_ANALYSIS_PROMPT


def test_chat_agent_prompt_has_jtbd() -> None:
    assert "Job To Be Done" in CHAT_AGENT_PROMPT


def test_chat_agent_prompt_has_boundaries() -> None:
    assert "NEVER" in CHAT_AGENT_PROMPT
    assert "Suggest code changes" in CHAT_AGENT_PROMPT
