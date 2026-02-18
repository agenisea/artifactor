"""Request/response schemas for the HTTP API."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """Standard response envelope for all API endpoints."""

    success: bool
    data: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectCreate(BaseModel):
    """Request body for POST /api/projects."""

    name: str = Field(min_length=1, max_length=200)
    local_path: str | None = None
    branch: str | None = None


class ChatRequest(BaseModel):
    """Request body for POST /api/projects/{id}/chat."""

    message: str = Field(min_length=1, max_length=10_000)
    conversation_id: str | None = None


class SectionExportRequest(BaseModel):
    """Query parameters for section export."""

    format: str = Field(
        default="markdown", pattern="^(markdown|html|pdf|json)$"
    )


class CitationResponse(BaseModel):
    """Citation in API response format."""

    file_path: str
    function_name: str | None
    line_start: int
    line_end: int
    confidence: float


class ChatSSEEvent(BaseModel):
    """Single SSE event for chat streaming."""

    event: Literal[
        "thinking", "tool_call", "delta", "complete", "error"
    ]
    data: dict[str, Any]


class AnalysisSSEEvent(BaseModel):
    """Single SSE event for analysis progress."""

    event: Literal["stage", "complete", "error"]
    data: dict[str, Any]


class PlaybookStepResponse(BaseModel):
    """Single step in a playbook."""

    description: str
    tool: str


class PlaybookMetaResponse(BaseModel):
    """Summary metadata for playbook gallery listing."""

    name: str
    title: str
    description: str
    agent: str
    difficulty: str
    estimated_time: str
    mcp_prompt: str
    tags: list[str]
    step_count: int
    tools_used: list[str]


class PlaybookDetailResponse(BaseModel):
    """Full playbook detail with steps and example prompt."""

    name: str
    title: str
    description: str
    agent: str
    difficulty: str
    estimated_time: str
    mcp_prompt: str
    tags: list[str]
    step_count: int
    tools_used: list[str]
    steps: list[PlaybookStepResponse]
    example_prompt: str
