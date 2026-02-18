"""RAG pipeline: query -> context assembly -> formatted context for agent.

Hybrid search: vector similarity (LanceDB) + keyword (SQL).
Falls back to keyword-only when no embeddings exist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import lancedb
from circuitbreaker import (
    CircuitBreakerError,
    circuit,  # pyright: ignore[reportUnknownVariableType]
)

from artifactor.analysis.llm.embedder import embed_text
from artifactor.config import SECTION_TITLES, Settings
from artifactor.constants import (
    CB_VECTOR_FAILURE_THRESHOLD,
    CB_VECTOR_RECOVERY_TIMEOUT,
    EMBEDDINGS_TABLE,
    RAG_MAX_CONTEXT_CHARS,
    RAG_RRF_K,
    RAG_VECTOR_DISTANCE_UPPER,
    RAG_VECTOR_SNIPPET_CHARS,
)
from artifactor.models.document import Document
from artifactor.models.entity import CodeEntityRecord
from artifactor.repositories.protocols import (
    DocumentRepository,
    EntityRepository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VectorResult:
    """A single vector search hit from LanceDB."""

    file_path: str
    symbol_name: str
    content: str
    start_line: int
    end_line: int
    distance: float


@dataclass(frozen=True)
class RetrievedContext:
    """Bundle of context assembled by the RAG pipeline."""

    entities: list[CodeEntityRecord] = field(
        default_factory=lambda: list[CodeEntityRecord]()
    )
    documents: list[Document] = field(
        default_factory=lambda: list[Document]()
    )
    vector_results: list[VectorResult] = field(
        default_factory=lambda: list[VectorResult]()
    )
    formatted: str = ""


_SECTION_PRIORITY = list(SECTION_TITLES)

_MAX_CONTEXT_CHARS = RAG_MAX_CONTEXT_CHARS


async def retrieve_context(
    query: str,
    project_id: str,
    entity_repo: EntityRepository,
    document_repo: DocumentRepository,
    settings: Settings | None = None,
    max_entities: int = 10,
) -> RetrievedContext:
    """Search entities and documents relevant to a query.

    Strategy (hybrid):
    1. Vector search via LanceDB (if embeddings exist).
    2. Keyword search on code entities via SQL.
    3. Merge + deduplicate results (vector first).
    4. Scan priority sections for keyword overlap.
    5. Format combined context for the agent.
    """
    cfg = settings or Settings()

    # Vector search (graceful fallback)
    vectors = await _search_vectors(query, cfg)

    # Keyword entity search
    entities = await _search_entities(
        query, project_id, entity_repo, max_entities
    )

    # Merge: vector results first, then keyword entities
    entities = _merge_results(vectors, entities, max_entities)

    # Document search (unchanged — section-level)
    documents = await _search_documents(
        query, project_id, document_repo
    )

    formatted = _format_context(entities, documents, vectors)
    return RetrievedContext(
        entities=entities,
        documents=documents,
        vector_results=vectors,
        formatted=formatted,
    )


@circuit(  # pyright: ignore[reportUntypedFunctionDecorator]
    failure_threshold=CB_VECTOR_FAILURE_THRESHOLD,
    recovery_timeout=CB_VECTOR_RECOVERY_TIMEOUT,
    expected_exception=Exception,
)
async def _guarded_vector_query(
    query_vec: list[float],
    settings: Settings,
) -> list[dict[str, Any]]:
    """Circuit-breaker-protected LanceDB vector search."""
    db = await lancedb.connect_async(settings.lancedb_uri)
    table_list = await db.list_tables()
    if EMBEDDINGS_TABLE not in table_list.tables:
        return []
    table = await db.open_table(EMBEDDINGS_TABLE)
    query_builder: Any = await table.search(  # pyright: ignore[reportUnknownMemberType]
        query_vec
    )
    raw: list[dict[str, Any]] = (
        await query_builder.distance_range(
            upper_bound=RAG_VECTOR_DISTANCE_UPPER
        ).limit(
            settings.rag_vector_top_k
        ).to_list()
    )
    return raw


async def _search_vectors(
    query: str,
    settings: Settings,
) -> list[VectorResult]:
    """Embed query and search LanceDB for similar chunks."""
    try:
        query_vec = await embed_text(query, settings)
        if not query_vec:
            return []

        raw = await _guarded_vector_query(query_vec, settings)

        results: list[VectorResult] = []
        for row in raw:
            r: dict[str, Any] = row
            try:
                results.append(
                    VectorResult(
                        file_path=str(r.get("file_path", "")),
                        symbol_name=str(
                            r.get("symbol_name", "")
                        ),
                        content=str(r.get("content", "")),
                        start_line=int(
                            r.get("start_line", 0)
                        ),
                        end_line=int(r.get("end_line", 0)),
                        distance=float(
                            r.get("_distance", 0.0)
                        ),
                    )
                )
            except (ValueError, TypeError):
                logger.warning(
                    "event=vector_result_coercion_failed"
                    " row=%r",
                    {
                        k: type(v).__name__
                        for k, v in r.items()
                    },
                )
                continue
        return results

    except CircuitBreakerError:
        logger.warning(
            "event=circuit_open component=vector_search action=skip"
        )
        return []
    except Exception:
        logger.warning(
            "event=vector_search_failed action=keyword_fallback",
            exc_info=True,
        )
        return []


def _reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = RAG_RRF_K,
) -> list[str]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion.

    Each item receives score = sum(1/(k + rank)) across all lists
    it appears in. Items appearing in multiple lists get boosted.

    Args:
        ranked_lists: Lists of item identifiers, each ordered by relevance.
        k: Smoothing constant (default 60, per original RRF paper).

    Returns:
        Combined list of item identifiers, ordered by fused score (descending).
    """
    scores: dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, item_id in enumerate(ranked_list):
            scores[item_id] = (
                scores.get(item_id, 0.0) + 1.0 / (k + rank)
            )
    return sorted(scores, key=lambda x: scores[x], reverse=True)


def _merge_results(
    vectors: list[VectorResult],
    entities: list[CodeEntityRecord],
    max_results: int,
) -> list[CodeEntityRecord]:
    """Merge vector and keyword results using Reciprocal Rank Fusion.

    When both vector and keyword results exist, RRF combines the
    two ranked lists so that items appearing in both get boosted.
    Falls back to simple entity ordering when no vectors exist.
    """
    if not vectors and not entities:
        return []
    if not vectors:
        return entities[:max_results]

    # Build ranked lists keyed by (file_path:start_line)
    vector_keys = [
        f"{v.file_path}:{v.start_line}" for v in vectors
    ]
    entity_keys = [
        f"{e.file_path}:{e.start_line}" for e in entities
    ]

    # RRF merge
    fused_order = _reciprocal_rank_fusion(
        [vector_keys, entity_keys]
    )

    # Build lookup for entities
    entity_lookup: dict[str, CodeEntityRecord] = {
        f"{e.file_path}:{e.start_line}": e for e in entities
    }

    # Return entities in fused order (skip vector-only results
    # that don't have a corresponding entity record)
    result: list[CodeEntityRecord] = []
    for key in fused_order:
        if key in entity_lookup and len(result) < max_results:
            result.append(entity_lookup[key])

    # Fill remaining slots with entities not in fused list
    seen = {f"{e.file_path}:{e.start_line}" for e in result}
    for entity in entities:
        key = f"{entity.file_path}:{entity.start_line}"
        if key not in seen and len(result) < max_results:
            result.append(entity)

    return result[:max_results]


async def _search_entities(
    query: str,
    project_id: str,
    entity_repo: EntityRepository,
    max_results: int,
) -> list[CodeEntityRecord]:
    """Keyword search across code entities."""
    keywords = _extract_keywords(query)
    results: list[CodeEntityRecord] = []
    seen_ids: set[str] = set()

    for keyword in keywords:
        entities = await entity_repo.search(
            project_id, keyword
        )
        for entity in entities:
            if entity.id not in seen_ids:
                seen_ids.add(entity.id)
                results.append(entity)
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break

    return results[:max_results]


async def _search_documents(
    query: str,
    project_id: str,
    document_repo: DocumentRepository,
) -> list[Document]:
    """Find documents whose section content matches query keywords."""
    keywords = _extract_keywords(query)
    lower_keywords = [k.lower() for k in keywords]
    matched: list[Document] = []

    for section_name in _SECTION_PRIORITY:
        doc = await document_repo.get_section(
            project_id, section_name
        )
        if doc is None:
            continue
        content_lower = doc.content.lower()
        if any(kw in content_lower for kw in lower_keywords):
            matched.append(doc)

    return matched


def _extract_keywords(query: str) -> list[str]:
    """Split query into meaningful keywords (>2 chars)."""
    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "and",
        "or",
        "not",
        "with",
        "this",
        "that",
        "from",
        "by",
        "it",
        "what",
        "how",
        "does",
        "do",
        "can",
        "where",
        "which",
        "who",
        "when",
    }
    words = query.strip().split()
    return [
        w
        for w in words
        if len(w) > 2 and w.lower() not in stop_words
    ]


def _format_context(
    entities: list[CodeEntityRecord],
    documents: list[Document],
    vectors: list[VectorResult] | None = None,
) -> str:
    """Format retrieved context into a text block for the agent."""
    parts: list[str] = []
    budget = _MAX_CONTEXT_CHARS

    # Vector results first (most semantically relevant)
    if vectors:
        parts.append("## Semantic Matches\n")
        for vr in vectors:
            label = vr.symbol_name or vr.file_path
            line = (
                f"- {label} at {vr.file_path}:"
                f"{vr.start_line}"
                f" (distance: {vr.distance:.3f})\n"
            )
            snippet = vr.content[:RAG_VECTOR_SNIPPET_CHARS]
            block = f"{line}  ```\n  {snippet}\n  ```\n"
            if len(block) > budget:
                break
            parts.append(block)
            budget -= len(block)

    if entities:
        parts.append("\n## Code Entities\n")
        for entity in entities:
            line = (
                f"- {entity.name} ({entity.entity_type}) "
                f"at {entity.file_path}:"
                f"{entity.start_line}\n"
            )
            if len(line) > budget:
                break
            parts.append(line)
            budget -= len(line)

    if documents:
        parts.append("\n## Documentation Sections\n")
        for doc in documents:
            header = f"### {doc.section_name}\n"
            content = doc.content
            if len(content) + len(header) > budget:
                content = content[
                    : max(0, budget - len(header) - 4)
                ]
                content += "\n..."
            parts.append(header)
            parts.append(content + "\n")
            budget -= len(header) + len(content) + 1
            if budget <= 0:
                break

    return "".join(parts) if parts else "No context found."
