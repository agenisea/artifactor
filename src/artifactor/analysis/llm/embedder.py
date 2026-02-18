"""Generate semantic embeddings for code chunks and store in LanceDB."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import lancedb
import litellm
from circuitbreaker import (
    CircuitBreakerError,
    circuit,  # pyright: ignore[reportUnknownVariableType]
)

from artifactor.config import Settings
from artifactor.constants import (
    CB_EMBED_FAILURE_THRESHOLD,
    CB_EMBED_RECOVERY_TIMEOUT,
    EMBED_CONTENT_SNIPPET_CHARS,
    EMBEDDINGS_TABLE,
    MAX_TOKENS_PER_BATCH,
    MAX_TOKENS_PER_CHUNK,
    MIN_EMBED_TOKENS,
    estimate_tokens,
)
from artifactor.ingestion.schemas import CodeChunk

logger = logging.getLogger(__name__)

# litellm stubs have partially unknown types — typed alias
if TYPE_CHECKING:
    _aembedding: Callable[..., Coroutine[Any, Any, Any]]
else:
    _aembedding = litellm.aembedding

@circuit(  # pyright: ignore[reportUntypedFunctionDecorator]
    failure_threshold=CB_EMBED_FAILURE_THRESHOLD,
    recovery_timeout=CB_EMBED_RECOVERY_TIMEOUT,
    expected_exception=Exception,
)
async def _guarded_embed(
    model: str, texts: list[str]
) -> Any:
    """Circuit-breaker-protected embedding call."""
    return await _aembedding(model=model, input=texts)


def _truncate(
    text: str, max_tokens: int = MAX_TOKENS_PER_CHUNK
) -> str:
    """Truncate text to stay within embedding token limit."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    logger.warning(
        "event=chunk_truncated original_len=%d max_chars=%d",
        len(text),
        max_chars,
    )
    return text[:max_chars]


def _batch_texts(
    texts: list[str],
    max_batch_tokens: int = MAX_TOKENS_PER_BATCH,
) -> list[list[tuple[int, str]]]:
    """Split texts into sub-batches that fit within API token limits."""
    batches: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    current_tokens = 0
    for i, text in enumerate(texts):
        est = estimate_tokens(text)
        if current and current_tokens + est > max_batch_tokens:
            batches.append(current)
            current = []
            current_tokens = 0
        current.append((i, text))
        current_tokens += est
    if current:
        batches.append(current)
    return batches


async def embed_text(
    text: str,
    settings: Settings | None = None,
) -> list[float]:
    """Embed a single text string. Returns empty list on failure."""
    cfg = settings or Settings()
    truncated = _truncate(text)
    try:
        response: Any = await _guarded_embed(
            cfg.litellm_embedding_model, [truncated]
        )
        vec: list[float] = response.data[0]["embedding"]
        return vec
    except CircuitBreakerError:
        logger.warning("event=circuit_open component=embedding action=skip")
        return []
    except Exception:
        logger.warning("event=embed_text_failed", exc_info=True)
        return []


async def embed_chunks(
    chunks: list[CodeChunk],
    settings: Settings | None = None,
) -> int:
    """Embed code chunks and store vectors in LanceDB.

    Returns the count of successfully embedded chunks.
    Chunks below the minimum token threshold are skipped.
    Failures are logged and skipped (graceful degradation).
    """
    if settings is None:
        settings = Settings()

    eligible = [
        c
        for c in chunks
        if estimate_tokens(c.content) >= MIN_EMBED_TOKENS
    ]
    if not eligible:
        return 0

    # Truncate each chunk text for safety
    texts = [_truncate(c.content) for c in eligible]

    # Split into sub-batches to stay under API token limits
    batches = _batch_texts(texts)

    # Embed each batch separately, accumulate vectors
    all_vectors: list[list[float]] = [[] for _ in eligible]
    for batch in batches:
        batch_texts = [text for _, text in batch]
        try:
            response: Any = await _guarded_embed(
                settings.litellm_embedding_model, batch_texts
            )
        except CircuitBreakerError:
            logger.warning(
                "event=circuit_open component=embedding"
                " action=skip_batch"
            )
            return 0
        except Exception:
            logger.warning(
                "event=embedding_api_failed", exc_info=True
            )
            return 0

        if len(response.data) != len(batch_texts):
            logger.warning(
                "event=embedding_count_mismatch"
                " vectors=%d chunks=%d",
                len(response.data),
                len(batch_texts),
            )
            return 0

        for (orig_idx, _), item in zip(
            batch, response.data, strict=True
        ):
            all_vectors[orig_idx] = item["embedding"]

    # Verify all vectors populated
    if any(len(v) == 0 for v in all_vectors):
        logger.warning("event=embedding_incomplete")
        return 0

    # Store in LanceDB
    try:
        records: list[dict[str, Any]] = []
        for chunk, vector in zip(
            eligible, all_vectors, strict=True
        ):
            records.append(
                {
                    "vector": vector,
                    "file_path": str(chunk.file_path),
                    "language": chunk.language,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "symbol_name": chunk.symbol_name or "",
                    "content": chunk.content[
                        :EMBED_CONTENT_SNIPPET_CHARS
                    ],
                }
            )

        db = await lancedb.connect_async(settings.lancedb_uri)
        table_list = await db.list_tables()
        if EMBEDDINGS_TABLE in table_list.tables:
            table = await db.open_table(EMBEDDINGS_TABLE)
            await table.add(records)  # type: ignore[arg-type]
        else:
            await db.create_table(  # type: ignore[arg-type]
                EMBEDDINGS_TABLE, records
            )

        return len(records)

    except Exception:
        logger.warning("event=lancedb_write_failed", exc_info=True)
        return 0
