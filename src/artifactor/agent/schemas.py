"""Pydantic response models for the chat agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CitationRef(BaseModel):
    """Citation in agent response — mirrors Citation value object."""

    file_path: str
    function_name: str | None = None
    line_start: int
    line_end: int
    confidence: float = 0.0


class ConfidenceRef(BaseModel):
    """Confidence score in agent response."""

    value: float
    source: str
    explanation: str


class AgentResponse(BaseModel):
    """Structured response returned by the chat agent."""

    message: str = Field(
        description="Natural language answer to the user's question"
    )
    citations: list[CitationRef] = Field(
        default_factory=lambda: list[CitationRef](),
        description="Source code references",
    )
    confidence: ConfidenceRef | None = Field(
        default=None,
        description="Overall confidence in the response",
    )
    tools_used: list[str] = Field(
        default_factory=lambda: list[str](),
        description="Names of tools invoked",
    )
