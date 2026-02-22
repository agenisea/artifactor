"""Pipeline orchestration — runs the full analysis pipeline."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from artifactor.analysis.llm.analyzer import (
    LLM_ANALYZABLE_LANGUAGES,
    run_llm_analysis,
)
from artifactor.analysis.llm.schemas import LLMAnalysisResult
from artifactor.analysis.pipeline import ParallelGroup, PipelineStage
from artifactor.analysis.quality.gate_config import (
    SECTION_GATES,
    SectionGateConfig,
)
from artifactor.analysis.quality.guardrails import verify_citations
from artifactor.analysis.quality.schemas import (
    QualityReport,
    ValidationResult,
)
from artifactor.analysis.quality.section_gate import (
    evaluate_section_gate,
)
from artifactor.analysis.quality.validator import cross_validate
from artifactor.analysis.static.analyzer import run_static_analysis
from artifactor.analysis.static.schemas import StaticAnalysisResult
from artifactor.config import SECTION_TITLES, Settings
from artifactor.constants import (
    ID_HEX_LENGTH,
    Confidence,
    StageOutcome,
    StageProgress,
)
from artifactor.ingestion.chunker import chunk_code
from artifactor.ingestion.git_connector import resolve_local_repo
from artifactor.ingestion.language_detector import detect_languages
from artifactor.ingestion.schemas import (
    ChunkedFiles,
    LanguageMap,
    RepoPath,
    RepoSource,
)
from artifactor.intelligence.model import (
    IntelligenceModel,
    build_intelligence_model,
)
from artifactor.observability.dispatcher import TraceDispatcher
from artifactor.observability.emitters import (
    emit_pipeline_end,
    emit_pipeline_start,
)
from artifactor.outputs import SECTION_GENERATORS
from artifactor.outputs.base import SectionOutput, make_degraded_section
from artifactor.repositories.checkpoint_repo import SqlCheckpointRepository
from artifactor.repositories.protocols import CheckpointRepository
from artifactor.services.events import ProgressCallback, StageEvent

logger = logging.getLogger(__name__)


@dataclass
class StageStatus:
    """Status of a pipeline stage."""

    name: str
    ok: bool
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class AnalysisResult:
    """Full result of a pipeline run."""

    project_id: str
    stages: list[StageStatus] = field(
        default_factory=lambda: list[StageStatus]()
    )
    sections: list[SectionOutput] = field(
        default_factory=lambda: list[SectionOutput]()
    )
    model: IntelligenceModel | None = None
    quality_report: QualityReport | None = None
    total_duration_ms: float = 0.0


@dataclass
class PipelineContext:
    """Shared mutable state passed through all pipeline stages.

    Each phase writes its outputs here; downstream phases read
    from earlier fields.  Replaces ad-hoc local variables in
    ``run_analysis()`` with an explicit, typed context object.

    INVARIANT: parallel stages write to disjoint fields.
    _static_stage writes ctx.static; _llm_stage writes ctx.llm.
    checkpoint_repo is shared read-only (method calls, not field
    reassignment).
    """

    project_id: str
    repo_path: Path
    settings: Settings
    branch: str = "main"
    dispatcher: TraceDispatcher | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None
    commit_sha: str | None = None
    on_progress: ProgressCallback | None = None
    checkpoint_repo: CheckpointRepository | None = None

    # Phase 1 outputs
    repo: RepoPath | None = None
    lang_map: LanguageMap | None = None
    chunks: ChunkedFiles | None = None

    # Phase 2+3 outputs
    static: StaticAnalysisResult | None = None
    llm: LLMAnalysisResult | None = None

    # Phase 4 outputs
    validation: ValidationResult | None = None
    model: IntelligenceModel | None = None

    # Phase 5 outputs
    sections: list[SectionOutput] = field(
        default_factory=lambda: list[SectionOutput]()
    )

    # Phase 6 outputs
    quality_report: QualityReport | None = None

    def report(self, event: StageEvent) -> None:
        """Emit a progress event if callback is set."""
        if self.on_progress:
            self.on_progress(event)

    def report_done(self, status: StageStatus) -> None:
        """Emit a DONE/ERROR event for a completed stage."""
        self.report(
            StageEvent(
                name=status.name,
                status=(
                    StageProgress.DONE
                    if status.ok
                    else StageProgress.ERROR
                ),
                duration_ms=status.duration_ms,
                message=status.error or "",
            )
        )


def _build_context(
    pid: str,
    repo_path: str | Path,
    cfg: Settings,
    branch: str,
    dispatcher: TraceDispatcher | None,
    session_factory: async_sessionmaker[AsyncSession] | None,
    on_progress: ProgressCallback | None,
) -> PipelineContext:
    """Create a PipelineContext with optional checkpoint repo."""
    cp_repo = None
    if session_factory is not None:
        cp_repo = SqlCheckpointRepository(session_factory)
    return PipelineContext(
        project_id=pid,
        repo_path=Path(repo_path),
        settings=cfg,
        branch=branch,
        dispatcher=dispatcher,
        session_factory=session_factory,
        on_progress=on_progress,
        checkpoint_repo=cp_repo,
    )


async def run_analysis(
    repo_path: str | Path,
    settings: Settings | None = None,
    sections: list[str] | None = None,
    branch: str = "main",
    on_progress: ProgressCallback | None = None,
    dispatcher: TraceDispatcher | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    project_id: str | None = None,
) -> AnalysisResult:
    """Run the full analysis pipeline.

    Phases:
      1. Ingestion: clone/copy -> detect languages -> chunk code
      2+3. Dual analysis: static + LLM (concurrent via ParallelGroup)
      4. Quality: cross-validate + build intelligence model
      5. Section generation: 13 generators (concurrent via ParallelGroup)
      6. Citation verification
      7. Persistence
    """
    cfg = settings or Settings()
    pid = project_id or uuid.uuid4().hex[:ID_HEX_LENGTH]
    result = AnalysisResult(project_id=pid)
    t0 = time.monotonic()
    trace_id = f"pipeline_{pid}"
    target_sections = sections or list(SECTION_TITLES)

    ctx = _build_context(
        pid,
        repo_path,
        cfg,
        branch,
        dispatcher,
        session_factory,
        on_progress,
    )

    if dispatcher:
        await emit_pipeline_start(
            dispatcher, trace_id, pid
        )

    if not await _phase_ingestion(ctx, result):
        return await _finalize(
            result, t0, dispatcher, trace_id, success=False
        )

    await _phase_dual_analysis(ctx, result)

    if not await _phase_quality(ctx, result):
        return await _finalize(
            result, t0, dispatcher, trace_id, success=False
        )

    await _phase_section_generation(
        ctx, result, target_sections
    )
    await _phase_citation_verification(ctx, result)
    await _phase_persistence(ctx, result)

    return await _finalize(
        result, t0, dispatcher, trace_id, success=True
    )


# -- Pipeline phase functions --


async def _phase_ingestion(
    ctx: PipelineContext,
    result: AnalysisResult,
) -> bool:
    """Phase 1: Resolve repo, detect languages, chunk code.

    Returns False if ingestion failed critically (no repo).
    """
    # 1a: Resolve repo
    ctx.report(
        StageEvent(
            name="ingestion_resolve",
            status=StageProgress.RUNNING,
            message="Resolving repository path...",
        )
    )
    repo, status = await _run_stage(
        "ingestion_resolve",
        lambda: resolve_local_repo(
            RepoSource(
                local_path=ctx.repo_path, branch=ctx.branch
            ),
            ctx.settings,
        ),
    )
    result.stages.append(status)
    ctx.report_done(status)
    if repo is None:
        return False
    ctx.repo = repo
    ctx.commit_sha = repo.commit_sha

    # 1b: Detect languages
    ctx.report(
        StageEvent(
            name="ingestion_detect",
            status=StageProgress.RUNNING,
            message="Detecting languages...",
        )
    )
    lang_map, status = _run_stage_sync(
        "ingestion_detect",
        lambda: detect_languages(repo, ctx.settings),
    )
    result.stages.append(status)
    ctx.lang_map = (
        lang_map if lang_map is not None else LanguageMap()
    )
    lang_count = len(ctx.lang_map.languages)
    file_count = sum(
        li.file_count for li in ctx.lang_map.languages
    )
    ctx.report(
        StageEvent(
            name="ingestion_detect",
            status=(
                StageProgress.DONE
                if status.ok
                else StageProgress.ERROR
            ),
            message=(
                f"Detected {lang_count} languages"
                f" across {file_count} files"
            ),
            duration_ms=status.duration_ms,
        )
    )

    # 1c: Chunk code
    ctx.report(
        StageEvent(
            name="ingestion_chunk",
            status=StageProgress.RUNNING,
            message="Chunking code...",
        )
    )
    chunks, status = _run_stage_sync(
        "ingestion_chunk",
        lambda: chunk_code(
            repo, ctx.lang_map or LanguageMap(), ctx.settings
        ),
    )
    result.stages.append(status)
    ctx.chunks = (
        chunks if chunks is not None else ChunkedFiles()
    )
    chunk_count = len(ctx.chunks.chunks)
    ctx.report(
        StageEvent(
            name="ingestion_chunk",
            status=(
                StageProgress.DONE
                if status.ok
                else StageProgress.ERROR
            ),
            message=(
                f"Created {chunk_count} chunks"
                f" from {ctx.chunks.total_files} files"
            ),
            duration_ms=status.duration_ms,
        )
    )

    return True


async def _phase_dual_analysis(
    ctx: PipelineContext,
    result: AnalysisResult,
) -> None:
    """Phase 2+3: Static + LLM analysis (concurrent via ParallelGroup)."""
    n_chunks = len(ctx.chunks.chunks) if ctx.chunks else 0
    n_code_chunks = (
        sum(
            1
            for c in ctx.chunks.chunks
            if c.language in LLM_ANALYZABLE_LANGUAGES
        )
        if ctx.chunks
        else 0
    )
    ctx.report(
        StageEvent(
            name="static_analysis",
            status=StageProgress.RUNNING,
            message=(
                f"Analyzing {n_chunks} chunks"
                f" (AST + call graph + deps)"
            ),
        )
    )
    ctx.report(
        StageEvent(
            name="llm_analysis",
            status=StageProgress.RUNNING,
            message=(
                f"Analyzing {n_code_chunks} code chunks"
                f" (embedding + narration + rules)"
            ),
        )
    )

    analysis_group: ParallelGroup[PipelineContext] = (
        ParallelGroup(
            name="dual_analysis",
            stages=[
                PipelineStage(
                    name="static_analysis",
                    execute=_static_stage,
                ),
                PipelineStage(
                    name="llm_analysis",
                    execute=_llm_stage,
                ),
            ],
        )
    )
    stage_results = await analysis_group.execute(ctx)
    for sr in stage_results:
        ss = StageStatus(
            name=sr.stage_name,
            ok=sr.status == StageOutcome.COMPLETED,
            duration_ms=sr.duration_ms,
            error=sr.error,
        )
        result.stages.append(ss)
        ctx.report_done(ss)

    if ctx.static is None:
        ctx.static = StaticAnalysisResult()
    if ctx.llm is None:
        ctx.llm = LLMAnalysisResult()


async def _phase_quality(
    ctx: PipelineContext,
    result: AnalysisResult,
) -> bool:
    """Phase 4: Cross-validate + build intelligence model.

    Returns False if model build failed.
    """
    ctx.report(
        StageEvent(
            name="quality",
            status=StageProgress.RUNNING,
            message="Cross-validating results...",
        )
    )
    validation, status = _run_stage_sync(
        "quality",
        lambda: cross_validate(
            ctx.static or StaticAnalysisResult(),
            ctx.llm or LLMAnalysisResult(),
        ),
    )
    result.stages.append(status)
    ctx.report_done(status)
    ctx.validation = (
        validation
        if validation is not None
        else ValidationResult()
    )

    ctx.report(
        StageEvent(
            name="intelligence_model",
            status=StageProgress.RUNNING,
            message="Building intelligence model...",
        )
    )
    model, status = _run_stage_sync(
        "intelligence_model",
        lambda: build_intelligence_model(
            ctx.project_id,
            ctx.validation or ValidationResult(),
            ctx.static or StaticAnalysisResult(),
            ctx.llm or LLMAnalysisResult(),
        ),
    )
    result.stages.append(status)
    ctx.report_done(status)
    if model is None:
        return False
    ctx.model = model
    result.model = model
    return True


async def _phase_section_generation(
    ctx: PipelineContext,
    result: AnalysisResult,
    target_sections: list[str],
) -> None:
    """Phase 5: Generate documentation sections (concurrent)."""
    ctx.report(
        StageEvent(
            name="section_generation",
            status=StageProgress.RUNNING,
            message=(
                f"Generating {len(target_sections)}"
                " documentation sections"
            ),
        )
    )

    section_stages: list[
        PipelineStage[PipelineContext, Any]
    ] = []
    for name in target_sections:
        gen = SECTION_GENERATORS.get(name)
        if gen is None:
            logger.warning(
                "event=unknown_section section=%s", name
            )
            continue
        section_stages.append(
            PipelineStage(
                name=f"generate_{name}",
                execute=_make_section_stage(gen, name),
            )
        )

    if section_stages:
        section_group: ParallelGroup[PipelineContext] = (
            ParallelGroup(
                name="section_generation",
                stages=section_stages,
                max_concurrency=(
                    ctx.settings.analysis_max_concurrency
                ),
            )
        )
        section_results = await section_group.execute(ctx)
        failed_sections: list[str] = []
        for sr in section_results:
            ss = StageStatus(
                name=sr.stage_name,
                ok=sr.status == StageOutcome.COMPLETED,
                duration_ms=sr.duration_ms,
                error=sr.error,
            )
            result.stages.append(ss)

            if (
                sr.status == StageOutcome.FAILED
                and sr.error
            ):
                sn = sr.stage_name.removeprefix(
                    "generate_"
                )
                ctx.sections.append(
                    make_degraded_section(sn, sr.error)
                )
                failed_sections.append(sn)

        if failed_sections:
            logger.warning(
                "event=partial_sections failed=%d"
                " names=%s",
                len(failed_sections),
                ",".join(failed_sections),
            )

    result.sections = list(ctx.sections)


async def _phase_citation_verification(
    ctx: PipelineContext,
    result: AnalysisResult,
) -> None:
    """Phase 6: Verify citations against source tree."""
    all_citations = [
        c
        for section in result.sections
        for c in section.citations
    ]
    if not all_citations:
        return

    ctx.report(
        StageEvent(
            name="citation_verification",
            status=StageProgress.RUNNING,
            message="Verifying citations...",
        )
    )
    guardrail_results, status = _run_stage_sync(
        "citation_verification",
        lambda: verify_citations(
            all_citations, ctx.repo_path
        ),
    )
    result.stages.append(status)
    ctx.report_done(status)
    if guardrail_results is not None:
        valid_count = sum(
            1 for r in guardrail_results if r.passed
        )
        result.quality_report = QualityReport(
            guardrail_results=guardrail_results,
            citations_checked=len(all_citations),
            citations_valid=valid_count,
            avg_confidence=_avg_confidence(
                result.sections
            ),
        )


async def _phase_persistence(
    ctx: PipelineContext,
    result: AnalysisResult,
) -> None:
    """Phase 7: Persist results to database."""
    if ctx.session_factory is None:
        return

    ctx.report(
        StageEvent(
            name="persistence",
            status=StageProgress.RUNNING,
            message=(
                f"Persisting {len(result.sections)}"
                " sections..."
            ),
        )
    )
    t_persist = time.monotonic()
    try:
        from artifactor.services.analysis_persistence import (
            AnalysisPersistenceService,
        )

        svc = AnalysisPersistenceService(
            ctx.session_factory
        )
        await svc.persist(ctx.project_id, result)
        ctx.report(
            StageEvent(
                name="persistence",
                status=StageProgress.DONE,
                message=(
                    f"Persisted {len(result.sections)}"
                    " sections"
                ),
                duration_ms=_elapsed(t_persist),
            )
        )
    except Exception:
        logger.exception(
            "event=persist_failed project_id=%s",
            ctx.project_id,
        )
        ctx.report(
            StageEvent(
                name="persistence",
                status=StageProgress.ERROR,
                message="Failed to persist results",
            )
        )


async def _finalize(
    result: AnalysisResult,
    t0: float,
    dispatcher: TraceDispatcher | None,
    trace_id: str,
    *,
    success: bool,
) -> AnalysisResult:
    """Set total duration and emit pipeline end trace."""
    result.total_duration_ms = _elapsed(t0)
    if dispatcher:
        await emit_pipeline_end(
            dispatcher,
            trace_id,
            result.total_duration_ms,
            success=success,
        )
    return result


# -- Context-based stage functions for ParallelGroup --


async def _static_stage(ctx: PipelineContext) -> None:
    """Phase 2: Run static analysis (AST + call graph + deps)."""
    if ctx.repo is None:
        raise RuntimeError(
            "_static_stage requires ctx.repo to be set by a prior stage"
        )
    ctx.static = await run_static_analysis(
        ctx.repo,
        ctx.chunks or ChunkedFiles(),
        ctx.lang_map or LanguageMap(),
    )


async def _llm_stage(ctx: PipelineContext) -> None:
    """Phase 3: Run LLM analysis (embed + narrate + rules + risks)."""
    ctx.llm = await run_llm_analysis(
        ctx.chunks or ChunkedFiles(),
        ctx.lang_map or LanguageMap(),
        ctx.settings,
        checkpoint_repo=ctx.checkpoint_repo,
        commit_sha=ctx.commit_sha,
        on_progress=ctx.on_progress,
        project_id=ctx.project_id,
    )


def _make_section_stage(
    gen: Callable[
        [IntelligenceModel, str, Settings],
        Awaitable[SectionOutput],
    ],
    section_name: str,
) -> Callable[[PipelineContext], Awaitable[None]]:
    """Create an async stage executor with quality gate validation."""
    config = SECTION_GATES.get(
        section_name, SectionGateConfig()
    )

    async def _execute(ctx: PipelineContext) -> None:
        if ctx.model is None:
            raise RuntimeError(
                f"_make_section_stage({section_name!r}) requires ctx.model "
                "to be set by a prior stage"
            )
        best_output: SectionOutput | None = None

        for attempt in range(config.max_iterations):
            output = await gen(
                ctx.model, ctx.project_id, ctx.settings
            )
            gate = evaluate_section_gate(
                section_name, output.content, config
            )

            if (
                gate.passed
                or attempt == config.max_iterations - 1
            ):
                adjusted = _compute_confidence(
                    output.confidence, gate.score
                )
                logger.info(
                    "event=section_gate section=%s"
                    " passed=%s score=%.2f"
                    " confidence=%.2f attempt=%d",
                    section_name,
                    gate.passed,
                    gate.score,
                    adjusted,
                    attempt + 1,
                )
                best_output = SectionOutput(
                    title=output.title,
                    section_name=output.section_name,
                    content=output.content,
                    confidence=adjusted,
                )
                break

            logger.warning(
                "event=section_gate_retry section=%s"
                " score=%.2f failures=%d attempt=%d",
                section_name,
                gate.score,
                len(gate.failures),
                attempt + 1,
            )

        if best_output is None:
            raise RuntimeError(
                f"Section '{section_name}' failed all "
                f"{config.max_iterations} quality gate iterations"
            )
        ctx.sections.append(best_output)

    return _execute


# -- Generic stage runners --


async def _run_stage[T](
    name: str,
    fn: Callable[[], Awaitable[T]],
) -> tuple[T | None, StageStatus]:
    """Run an async stage with error capture."""
    t0 = time.monotonic()
    try:
        out = await fn()
        return out, StageStatus(
            name=name, ok=True, duration_ms=_elapsed(t0)
        )
    except Exception as exc:
        logger.exception("event=stage_failed stage=%s", name)
        return None, StageStatus(
            name=name,
            ok=False,
            duration_ms=_elapsed(t0),
            error=str(exc),
        )


def _run_stage_sync[T](
    name: str,
    fn: Callable[[], T],
) -> tuple[T | None, StageStatus]:
    """Run a sync stage with error capture."""
    t0 = time.monotonic()
    try:
        out = fn()
        return out, StageStatus(
            name=name, ok=True, duration_ms=_elapsed(t0)
        )
    except Exception as exc:
        logger.exception("event=stage_failed stage=%s", name)
        return None, StageStatus(
            name=name,
            ok=False,
            duration_ms=_elapsed(t0),
            error=str(exc),
        )


def _compute_confidence(
    base_confidence: float,
    gate_score: float,
) -> float:
    """Combine base confidence with gate score.

    Generators set base: 0.90 (LLM), 0.80 (LLM sparse context),
    0.50 (template fallback). Pipeline multiplies by gate score.
    """
    confidence = base_confidence * gate_score
    return max(Confidence.FLOOR, min(Confidence.CEILING, confidence))


def _avg_confidence(sections: list[SectionOutput]) -> float:
    """Average confidence across generated sections."""
    values = [s.confidence for s in sections if s.confidence > 0]
    return sum(values) / len(values) if values else 0.0


def _elapsed(t0: float) -> float:
    return (time.monotonic() - t0) * 1000
