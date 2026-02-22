"""Orchestrate all LLM analysis modules."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

from artifactor.analysis.llm.combined import CombinedResult, analyze_chunk
from artifactor.analysis.llm.embedder import embed_chunks
from artifactor.analysis.llm.schemas import (
    BusinessRule,
    LLMAnalysisResult,
    ModuleNarrative,
    RiskIndicator,
)
from artifactor.config import Settings
from artifactor.ingestion.schemas import ChunkedFiles, CodeChunk, LanguageMap
from artifactor.repositories.protocols import CheckpointRepository
from artifactor.services.events import StageEvent

logger = logging.getLogger(__name__)

# Languages that warrant full LLM analysis (narrative + rules + risks).
# Data/config/markup languages are embedded for RAG but skipped here.
LLM_ANALYZABLE_LANGUAGES: set[str] = {
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
    "rust",
    "c",
    "cpp",
    "c_sharp",
    "ruby",
    "php",
    "swift",
    "kotlin",
    "scala",
    "lua",
    "bash",
    "elixir",
    "haskell",
    "ocaml",
    "r",
    "dart",
    "zig",
}


def _chunk_hash(chunk: CodeChunk) -> str:
    """Compute a stable hash for a code chunk (null-byte delimited)."""
    payload = (
        f"{chunk.file_path}\x00{chunk.start_line}"
        f"\x00{chunk.end_line}\x00{chunk.content}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def _try_checkpoint_lookup(
    checkpoint_repo: CheckpointRepository,
    project_id: str,
    chunk_hash: str,
) -> CombinedResult | None:
    """Look up a cached checkpoint and deserialize it."""
    cp = await checkpoint_repo.get(project_id, chunk_hash)
    if cp is None:
        return None

    try:
        data: dict[str, Any] = json.loads(cp.result_json)
        narrative = ModuleNarrative(
            file_path=data.get("file_path", ""),
            purpose=data.get("purpose", ""),
            confidence=data.get("confidence", "medium"),
            behaviors=data.get("behaviors", []),
            domain_concepts=data.get("domain_concepts", []),
            citations=data.get("citations", []),
        )
        rules = [
            BusinessRule(**r) for r in data.get("rules", [])
        ]
        risks = [
            RiskIndicator(**r) for r in data.get("risks", [])
        ]
        return (narrative, rules, risks)
    except Exception:
        logger.warning(
            "event=checkpoint_deserialize_failed hash=%s",
            chunk_hash,
        )
        return None


def _serialize_result(
    result: CombinedResult, file_path: str
) -> str:
    """Serialize a CombinedResult to JSON for checkpoint storage."""
    narrative, rules, risks = result
    data = {
        "file_path": file_path,
        "purpose": narrative.purpose,
        "confidence": narrative.confidence,
        "behaviors": narrative.behaviors,
        "domain_concepts": narrative.domain_concepts,
        "citations": narrative.citations,
        "rules": [
            {
                "rule_text": r.rule_text,
                "rule_type": r.rule_type,
                "condition": r.condition,
                "consequence": r.consequence,
                "confidence": r.confidence,
                "affected_entities": r.affected_entities,
                "citations": r.citations,
            }
            for r in rules
        ],
        "risks": [
            {
                "risk_type": r.risk_type,
                "severity": r.severity,
                "title": r.title,
                "description": r.description,
                "file_path": r.file_path,
                "line": r.line,
                "recommendations": r.recommendations,
                "confidence": r.confidence,
            }
            for r in risks
        ],
    }
    return json.dumps(data)


async def run_llm_analysis(
    chunked_files: ChunkedFiles,
    language_map: LanguageMap,
    settings: Settings | None = None,
    checkpoint_repo: CheckpointRepository | None = None,
    commit_sha: str | None = None,
    on_progress: Callable[[StageEvent], None] | None = None,
    project_id: str | None = None,
) -> LLMAnalysisResult:
    """Run all LLM analysis modules with bounded concurrency.

    1. Embed all chunks (including config/data files for RAG)
    2. Combined analysis per code chunk only (skip JSON, YAML, etc.)
       - With checkpoint support: skip chunks already analyzed

    Each module has independent error recovery — failure produces
    empty results, not a crash.
    """
    if settings is None:
        settings = Settings()

    # 1. Embed all chunks (including config/data for RAG search)
    try:
        embedded_count = await embed_chunks(
            chunked_files.chunks, settings
        )
    except Exception:
        logger.warning("event=embedding_failed stage=embed_chunks")
        embedded_count = 0

    # 2. Combined analysis — only for code languages (not JSON/YAML/CSS/etc.)
    code_chunks = [
        c
        for c in chunked_files.chunks
        if c.language in LLM_ANALYZABLE_LANGUAGES
    ]
    skipped = len(chunked_files.chunks) - len(code_chunks)
    if skipped > 0:
        logger.info(
            "event=llm_analysis_skip_non_code skipped=%d code=%d",
            skipped,
            len(code_chunks),
        )

    # Check how many are already checkpointed
    total_code = len(code_chunks)
    # Safe: incremented between await points in cooperative asyncio.
    # Only used for logging — no correctness dependency.
    resumed_count = 0

    semaphore = asyncio.Semaphore(settings.llm_max_concurrency)
    all_narratives: list[ModuleNarrative] = []
    all_rules: list[BusinessRule] = []
    all_risks: list[RiskIndicator] = []
    completed_count = 0

    async def process_chunk(chunk: CodeChunk) -> None:
        nonlocal completed_count, resumed_count
        async with semaphore:
            lang = chunk.language
            c_hash = _chunk_hash(chunk)
            file_path = str(chunk.file_path)

            # Try checkpoint lookup
            if checkpoint_repo:
                cached = await _try_checkpoint_lookup(
                    checkpoint_repo,
                    project_id or "",
                    c_hash,
                )
                if cached is not None:
                    narrative, rules, risks = cached
                    all_narratives.append(narrative)
                    all_rules.extend(rules)
                    all_risks.extend(risks)
                    resumed_count += 1
                    logger.debug(
                        "event=checkpoint_hit file=%s",
                        chunk.file_path,
                    )
                    completed_count += 1
                    _emit_progress(
                        on_progress,
                        completed_count,
                        total_code,
                    )
                    return

            try:
                result = await analyze_chunk(
                    chunk, lang, settings
                )
                narrative, rules, risks = result
                all_narratives.append(narrative)
                all_rules.extend(rules)
                all_risks.extend(risks)

                # Write checkpoint
                if checkpoint_repo and commit_sha:
                    from artifactor.models.checkpoint import (
                        AnalysisCheckpoint,
                    )

                    await checkpoint_repo.put(
                        AnalysisCheckpoint(
                            project_id=project_id or "",
                            commit_sha=commit_sha,
                            chunk_hash=c_hash,
                            file_path=file_path,
                            result_json=_serialize_result(
                                result, file_path
                            ),
                        )
                    )
            except Exception:
                logger.warning(
                    "event=combined_analysis_failed file=%s",
                    chunk.file_path,
                )

            completed_count += 1
            _emit_progress(
                on_progress, completed_count, total_code
            )

    tasks = [
        process_chunk(chunk) for chunk in code_chunks
    ]

    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=settings.analysis_timeout_seconds,
        )
    except TimeoutError:
        timeout = settings.analysis_timeout_seconds
        logger.warning(
            "event=llm_analysis_timeout timeout_s=%d", timeout
        )

    if resumed_count > 0:
        logger.info(
            "event=checkpoint_resume_complete resumed=%d total=%d",
            resumed_count,
            total_code,
        )

    from artifactor.constants import ConfidenceLevel

    degraded = sum(
        1 for n in all_narratives
        if n.confidence == ConfidenceLevel.LOW
    )
    if degraded > 0:
        logger.warning(
            "event=llm_degraded_results degraded=%d"
            " total=%d pct=%.0f%%",
            degraded,
            len(all_narratives),
            (degraded / len(all_narratives) * 100)
            if all_narratives
            else 0,
        )

    return LLMAnalysisResult(
        narratives=all_narratives,
        business_rules=all_rules,
        risks=all_risks,
        embeddings_stored=embedded_count,
    )


def _emit_progress(
    on_progress: Callable[[StageEvent], None] | None,
    completed: int,
    total: int,
) -> None:
    """Emit a progress event for the LLM analysis stage."""
    if on_progress is None or total == 0:
        return
    from artifactor.constants import StageProgress

    percent = round((completed / total) * 100, 1)
    on_progress(
        StageEvent(
            name="llm_analysis",
            status=StageProgress.RUNNING,
            message=f"Analyzed {completed}/{total} code chunks",
            completed=completed,
            total=total,
            percent=percent,
        )
    )
