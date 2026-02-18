"""Tests for the guardrails module."""

from pathlib import Path

import pytest

from artifactor.analysis.quality.guardrails import (
    gate_low_confidence_output,
    validate_chat_input,
    verify_citations,
)
from artifactor.intelligence.value_objects import Citation


class TestVerifyCitations:
    def test_valid_citation(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("line1\nline2\nline3\n")
        citation = Citation(
            file_path="main.py",
            function_name="greet",
            line_start=1,
            line_end=3,
            confidence=0.9,
        )
        results = verify_citations([citation], tmp_path)
        assert len(results) == 1
        assert results[0].passed is True

    def test_file_not_found(self, tmp_path: Path) -> None:
        citation = Citation(
            file_path="missing.py",
            function_name=None,
            line_start=1,
            line_end=1,
            confidence=0.9,
        )
        results = verify_citations([citation], tmp_path)
        assert results[0].passed is False
        assert "not found" in (results[0].reason or "").lower()

    def test_line_start_below_one(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("line1\n")
        citation = Citation(
            file_path="main.py",
            function_name=None,
            line_start=0,
            line_end=1,
            confidence=0.9,
        )
        results = verify_citations([citation], tmp_path)
        assert results[0].passed is False

    def test_line_end_exceeds_file(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("line1\nline2\n")
        citation = Citation(
            file_path="main.py",
            function_name=None,
            line_start=1,
            line_end=100,
            confidence=0.9,
        )
        results = verify_citations([citation], tmp_path)
        assert results[0].passed is False
        assert "exceeds" in (results[0].reason or "").lower()

    def test_line_end_before_start(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("line1\nline2\n")
        citation = Citation(
            file_path="main.py",
            function_name=None,
            line_start=5,
            line_end=2,
            confidence=0.9,
        )
        results = verify_citations([citation], tmp_path)
        assert results[0].passed is False


class TestValidateChatInput:
    def test_normal_input(self) -> None:
        assert validate_chat_input("  hello  ") == "hello"

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_chat_input("   ")

    def test_long_input_truncated(self) -> None:
        long_text = "x" * 20_000
        result = validate_chat_input(long_text)
        assert len(result) == 10_000


class TestGateLowConfidence:
    def test_above_threshold_passes_through(self) -> None:
        content, gated = gate_low_confidence_output(
            "All good", 0.9
        )
        assert content == "All good"
        assert gated is False

    def test_below_threshold_adds_disclaimer(self) -> None:
        content, gated = gate_low_confidence_output(
            "Maybe", 0.4
        )
        assert gated is True
        assert "[Low confidence: 0.40]" in content
        assert "Maybe" in content

    def test_exact_threshold_passes(self) -> None:
        _, gated = gate_low_confidence_output("ok", 0.6)
        assert gated is False
