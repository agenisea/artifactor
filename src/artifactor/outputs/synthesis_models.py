"""Pydantic validation models for section synthesis output."""

from pydantic import BaseModel, field_validator

from artifactor.constants import SECTION_MIN_LENGTH


class SectionMarkdown(BaseModel):
    """Structured validation for LLM section output.

    Validates that synthesized section content meets minimum quality
    thresholds before it's accepted into the output pipeline.
    Extensible -- add field_validators here for additional rules
    (max_length, heading structure, etc.) without modifying the
    synthesizer loop.
    """

    content: str

    @field_validator("content")
    @classmethod
    def _validate_content(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < SECTION_MIN_LENGTH:
            msg = (
                f"Section content too short "
                f"({len(stripped)} chars, "
                f"min {SECTION_MIN_LENGTH})"
            )
            raise ValueError(msg)
        return stripped
