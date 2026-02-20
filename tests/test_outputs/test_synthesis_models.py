"""Tests for SectionMarkdown Pydantic validation model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from artifactor.constants import SECTION_MIN_LENGTH
from artifactor.outputs.synthesis_models import SectionMarkdown


class TestSectionMarkdown:
    def test_accepts_content_at_min_length(self) -> None:
        text = "x" * SECTION_MIN_LENGTH
        result = SectionMarkdown(content=text)
        assert result.content == text

    def test_rejects_content_below_min_length(self) -> None:
        text = "x" * (SECTION_MIN_LENGTH - 1)
        with pytest.raises(ValidationError, match="too short"):
            SectionMarkdown(content=text)

    def test_strips_whitespace_from_content(self) -> None:
        text = "  " + "x" * SECTION_MIN_LENGTH + "  \n"
        result = SectionMarkdown(content=text)
        assert result.content == "x" * SECTION_MIN_LENGTH

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValidationError, match="too short"):
            SectionMarkdown(content="")
