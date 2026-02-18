"""Tests for section quality gate and placeholder detection."""

from __future__ import annotations

import pytest

from artifactor.analysis.quality.gate_config import (
    SECTION_GATES,
    SectionGateConfig,
)
from artifactor.analysis.quality.section_gate import (
    GateResult,
    detect_placeholders,
    evaluate_section_gate,
)
from artifactor.config import SECTION_TITLES

# ── Placeholder detection ────────────────────────────────────


def test_detects_known_placeholders() -> None:
    """Known placeholders like [TODO] and [PROJECT NAME] are found."""
    content = "This is a [TODO] and also [PROJECT NAME] here."
    found = detect_placeholders(content)
    assert "[TODO]" in found
    assert "[PROJECT NAME]" in found


def test_detects_keyword_placeholders() -> None:
    """Placeholder-keyword matches (e.g. [INSERT VALUE]) are found."""
    content = "Please [INSERT VALUE] into the form."
    found = detect_placeholders(content)
    assert "[INSERT VALUE]" in found


def test_ignores_code_blocks() -> None:
    """Placeholders inside fenced code blocks are skipped."""
    content = "Normal text.\n```\n[TODO] inside code\n```\nMore text."
    found = detect_placeholders(content)
    assert found == []


def test_ignores_inline_code() -> None:
    """Placeholders inside inline code are skipped."""
    content = "Use `[TODO]` as the marker and move on."
    found = detect_placeholders(content)
    assert found == []


def test_ignores_normal_brackets() -> None:
    """Checkboxes [x] and markdown links [text](url) are not placeholders."""
    content = "- [x] Done\n- [link](https://example.com)"
    found = detect_placeholders(content)
    assert found == []


def test_returns_specific_placeholders() -> None:
    """Returns list of specific placeholder strings, not just count."""
    content = "See [TODO] and [TBD] for details."
    found = detect_placeholders(content)
    assert isinstance(found, list)
    assert len(found) == 2
    assert "[TODO]" in found
    assert "[TBD]" in found


# ── Gate evaluator ───────────────────────────────────────────


def test_section_gate_passes_good_content() -> None:
    """Content meeting all thresholds passes the gate."""
    config = SectionGateConfig(min_length=50)
    content = "A" * 100  # well above min_length, no placeholders
    result = evaluate_section_gate("test", content, config)
    assert result.passed is True
    assert result.score > 0.0


def test_section_gate_fails_short_content() -> None:
    """Content below min_length fails with error severity."""
    config = SectionGateConfig(min_length=200)
    content = "Short."
    result = evaluate_section_gate("test", content, config)
    assert result.passed is False
    assert any(
        f.field == "content_length" for f in result.failures
    )


def test_section_gate_detects_placeholders() -> None:
    """Content with unfilled placeholders fails."""
    config = SectionGateConfig(
        min_length=10, check_placeholders=True
    )
    content = "A" * 50 + " [PROJECT NAME] should be replaced."
    result = evaluate_section_gate("test", content, config)
    assert result.passed is False
    assert any(
        f.field == "placeholders" for f in result.failures
    )


def test_section_gate_detects_repetition() -> None:
    """Duplicate paragraphs trigger a warning."""
    paragraph = "A" * 60  # > 50 chars required
    config = SectionGateConfig(
        min_length=10, check_repetition=True
    )
    content = f"{paragraph}\n\n{paragraph}"
    result = evaluate_section_gate("test", content, config)
    assert any(
        f.field == "repetition" for f in result.failures
    )


def test_section_gate_checks_required_headings() -> None:
    """Missing required headings produce a warning failure."""
    config = SectionGateConfig(
        min_length=10,
        required_headings=("Overview", "Details"),
    )
    content = "A" * 50 + "\n## Overview\nSome content."
    result = evaluate_section_gate("test", content, config)
    assert any(
        f.field == "required_headings"
        for f in result.failures
    )
    # "Details" is missing
    failure = next(
        f
        for f in result.failures
        if f.field == "required_headings"
    )
    assert "Details" in failure.actual


def test_section_gate_uses_config() -> None:
    """Custom SectionGateConfig thresholds are respected."""
    config = SectionGateConfig(min_length=50)
    content = "A" * 60  # above 50, passes
    result = evaluate_section_gate("test", content, config)
    assert result.passed is True

    config2 = SectionGateConfig(min_length=100)
    result2 = evaluate_section_gate("test", content, config2)
    assert result2.passed is False


# ── Gate config registry ─────────────────────────────────────


def test_all_sections_have_gate_config() -> None:
    """Every section name has a gate config entry."""
    for name in SECTION_TITLES:
        assert name in SECTION_GATES, (
            f"Section {name!r} missing from SECTION_GATES"
        )


def test_gate_config_immutable() -> None:
    """SectionGateConfig is frozen — assignment raises."""
    config = SectionGateConfig()
    with pytest.raises(AttributeError):
        config.min_length = 999  # type: ignore[misc]


def test_default_max_iterations() -> None:
    """Default SectionGateConfig has max_iterations == 2."""
    config = SectionGateConfig()
    assert config.max_iterations == 2


def test_gate_result_is_frozen() -> None:
    """GateResult is frozen — assignment raises."""
    result = GateResult(
        section_name="test", passed=True, score=1.0
    )
    with pytest.raises(AttributeError):
        result.passed = False  # type: ignore[misc]
