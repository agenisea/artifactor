"""Shared constants — single source of truth for cross-module values.

All magic strings and numbers that appear in 2+ files belong here.
StrEnum members are str-compatible, so downstream code (JSON, SQL,
SSE payloads) works unchanged.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

# ── String Enums ─────────────────────────────────────────


class ProjectStatus(StrEnum):
    """Project lifecycle status."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    ERROR = "error"
    PAUSED = "paused"


class SSEEvent(StrEnum):
    """Server-Sent Event type names."""

    STAGE = "stage"
    COMPLETE = "complete"
    ERROR = "error"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    PAUSED = "paused"


class StageProgress(StrEnum):
    """Progress status for pipeline stage events.

    Named StageProgress (not StageStatus) to avoid collision
    with the StageStatus dataclass in analysis_service.py.
    """

    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class StageOutcome(StrEnum):
    """Outcome of an individual pipeline stage execution.

    Named StageOutcome (not PipelineResult) because these
    values describe per-stage outcomes, not overall pipeline results.
    """

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RelationshipType(StrEnum):
    """Edge types in the knowledge graph."""

    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    USES = "uses"


class ConfidenceLevel(StrEnum):
    """Qualitative confidence labels from LLM analysis."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Severity(StrEnum):
    """Severity levels for quality gate failures and risk indicators."""

    ERROR = "error"
    WARNING = "warning"


class ExportFormat(StrEnum):
    """Supported document export formats."""

    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    PDF = "pdf"


class SectionName(StrEnum):
    """Canonical section identifiers for document generation."""

    EXECUTIVE_OVERVIEW = "executive_overview"
    FEATURES = "features"
    PERSONAS = "personas"
    USER_STORIES = "user_stories"
    SECURITY_REQUIREMENTS = "security_requirements"
    SYSTEM_OVERVIEW = "system_overview"
    DATA_MODELS = "data_models"
    INTERFACES = "interfaces"
    UI_SPECS = "ui_specs"
    API_SPECS = "api_specs"
    INTEGRATIONS = "integrations"
    TECH_STORIES = "tech_stories"
    SECURITY_CONSIDERATIONS = "security_considerations"


# Type alias for analysis source provenance
type AnalysisSource = Literal["ast", "llm", "cross_validated"]


# ── Confidence Thresholds ────────────────────────────────


class Confidence:
    """Named confidence thresholds — single source of truth."""

    CROSS_VALIDATED_HIGH = 0.95  # AST + LLM agree
    AST_ONLY = 0.90  # Deterministic parser
    CROSS_VALIDATED_MEDIUM = 0.85  # Partial agreement
    LLM_SECTION_RICH = 0.90  # Section gen w/ rich context
    LLM_SECTION_SPARSE = 0.80  # Section gen w/ sparse context
    LLM_ONLY = 0.70  # Probabilistic inference
    WORKFLOW_DEFAULT = 0.60  # Workflow confidence
    CROSS_VALIDATED_LOW = 0.50  # AST + LLM disagree
    GUARDRAIL_THRESHOLD = 0.60  # Low confidence gating
    FLOOR = 0.10  # Pipeline minimum
    CEILING = 0.95  # Pipeline maximum
    RELATIONSHIP_DEFAULT = 0.95  # Default relationship confidence


MIN_CONTEXT_ITEMS = 3  # Rich vs sparse context threshold


def confidence_from_level(level: str) -> float:
    """Map LLM confidence level ('high'/'medium'/'low') to numeric score.

    Eliminates the 3x repeated ternary pattern in model.py:
        0.9 if x == "high" else 0.7 if x == "medium" else 0.5
    """
    _map: dict[str, float] = {
        ConfidenceLevel.HIGH: Confidence.AST_ONLY,
        ConfidenceLevel.MEDIUM: Confidence.LLM_ONLY,
    }
    return _map.get(level, Confidence.CROSS_VALIDATED_LOW)


# ── Named Constants ──────────────────────────────────────

# LanceDB table name
EMBEDDINGS_TABLE = "embeddings"

# ── Circuit Breaker Configuration ────────────────────────

CB_LLM_FAILURE_THRESHOLD = 5
CB_LLM_RECOVERY_TIMEOUT = 30
CB_EMBED_FAILURE_THRESHOLD = 3
CB_EMBED_RECOVERY_TIMEOUT = 30
CB_VECTOR_FAILURE_THRESHOLD = 3
CB_VECTOR_RECOVERY_TIMEOUT = 60

# ── Retry Strategy ───────────────────────────────────────

RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_WAIT = 2
RETRY_MAX_WAIT = 30

# ── LLM Output ───────────────────────────────────────────

LLM_MAX_OUTPUT_TOKENS = 4096

# ── Embedding Limits ─────────────────────────────────────

MIN_EMBED_TOKENS = 10
MAX_TOKENS_PER_CHUNK = 8000  # text-embedding-3-small max is 8191
MAX_TOKENS_PER_BATCH = 250_000  # OpenAI batch limit is ~300K
EMBED_CONTENT_SNIPPET_CHARS = 2000

# ── RAG ──────────────────────────────────────────────────

RAG_MAX_CONTEXT_CHARS = 12_000
RAG_RRF_K = 60
RAG_VECTOR_DISTANCE_UPPER = 1.5
RAG_VECTOR_SNIPPET_CHARS = 400

# ── Misc ─────────────────────────────────────────────────

GIT_REVPARSE_TIMEOUT = 10
SSE_POLL_TIMEOUT = 0.5
BINARY_DETECTION_BUFFER = 8192
ERROR_TRUNCATION_CHARS = 200

# ── Auth Exempt Paths ────────────────────────────────────

AUTH_EXEMPT_PATHS = frozenset({
    "/api/health",
    "/api/docs",
    "/api/redoc",
    "/openapi.json",
})

AUTH_EXEMPT_PREFIXES = ("/api/health",)

# ── ID Generation ───────────────────────────────────────

ID_HEX_LENGTH = 12
SHORT_ID_HEX_LENGTH = 8

# ── Token Estimation ────────────────────────────────────

CHARS_PER_TOKEN_ESTIMATE = 4


def estimate_tokens(text: str) -> int:
    """Rough token estimate using chars-per-token ratio."""
    return len(text) // CHARS_PER_TOKEN_ESTIMATE


# ── Diagram Limits ──────────────────────────────────────

ARCH_DIAGRAM_MAX_RELATIONSHIPS = 50
ARCH_DIAGRAM_MAX_ENTITIES = 20
SEQUENCE_DIAGRAM_MAX_CALLS = 30

# ── Intent Router ──────────────────────────────────────

SEARCH_PRIORITY_WEIGHT = 1.5

# ── Call Graph ─────────────────────────────────────────

CALL_GRAPH_MIN_DEPTH = 1
CALL_GRAPH_MAX_DEPTH = 5
CALL_GRAPH_DEFAULT_DEPTH = 2
CALL_GRAPH_DEFAULT_DIRECTION = "both"

# ── Section Validation ─────────────────────────────────

SECTION_MIN_LENGTH = 50

# ── Stage Labels (user-facing) ─────────────────────────

STAGE_LABELS: dict[str, str] = {
    "ingestion_resolve": "Scanning codebase",
    "ingestion_detect": "Detecting languages",
    "ingestion_chunk": "Splitting source files",
    "static_analysis": "Parsing code structure",
    "llm_analysis": "AI analysis",
    "dual_analysis": "Cross-validating findings",
    "quality": "Scoring confidence",
    "intelligence_model": "Building Intelligence Model",
    "section_generation": "Generating documentation",
    "citation_verification": "Verifying citations",
    "persistence": "Saving results",
}
