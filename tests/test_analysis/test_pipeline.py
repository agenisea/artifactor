"""Tests for the typed pipeline framework."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from artifactor.analysis.pipeline import (
    ParallelGroup,
    PipelineStage,
)
from artifactor.analysis.quality.guardrails import verify_citations
from artifactor.analysis.quality.schemas import QualityReport
from artifactor.config import Settings
from artifactor.constants import STAGE_LABELS, StageOutcome
from artifactor.intelligence.value_objects import Citation
from artifactor.outputs.base import SectionOutput
from artifactor.services.analysis_service import (
    AnalysisResult,
    PipelineContext,
    _avg_confidence,
)


async def _succeed(data: str) -> str:
    return f"ok:{data}"


async def _fail(data: str) -> str:
    msg = "intentional"
    raise ValueError(msg)


async def _slow(data: str) -> str:
    await asyncio.sleep(0.05)
    return f"slow:{data}"


class TestPipelineStage:
    @pytest.mark.asyncio
    async def test_successful_run(self) -> None:
        stage: PipelineStage[str, str] = PipelineStage(
            name="test", execute=_succeed
        )
        result = await stage.run("hello")
        assert result.status == StageOutcome.COMPLETED
        assert result.output == "ok:hello"
        assert result.duration_ms >= 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_failed_run(self) -> None:
        stage: PipelineStage[str, str] = PipelineStage(
            name="failing", execute=_fail
        )
        result = await stage.run("hello")
        assert result.status == StageOutcome.FAILED
        assert result.output is None
        assert result.error == "intentional"

    @pytest.mark.asyncio
    async def test_duration_tracked(self) -> None:
        stage: PipelineStage[str, str] = PipelineStage(
            name="slow", execute=_slow
        )
        result = await stage.run("data")
        assert result.duration_ms >= 40


class TestParallelGroup:
    @pytest.mark.asyncio
    async def test_all_succeed(self) -> None:
        group: ParallelGroup[str] = ParallelGroup(
            name="group",
            stages=[
                PipelineStage(name="a", execute=_succeed),
                PipelineStage(name="b", execute=_succeed),
            ],
        )
        results = await group.execute("test")
        assert len(results) == 2
        assert all(r.status == StageOutcome.COMPLETED for r in results)

    @pytest.mark.asyncio
    async def test_failure_does_not_cancel_siblings(self) -> None:
        group: ParallelGroup[str] = ParallelGroup(
            name="mixed",
            stages=[
                PipelineStage(name="good", execute=_succeed),
                PipelineStage(name="bad", execute=_fail),
                PipelineStage(name="also_good", execute=_succeed),
            ],
        )
        results = await group.execute("test")
        assert len(results) == 3
        assert results[0].status == "completed"
        assert results[1].status == "failed"
        assert results[2].status == "completed"

    @pytest.mark.asyncio
    async def test_empty_group(self) -> None:
        group: ParallelGroup[str] = ParallelGroup(
            name="empty", stages=[]
        )
        results = await group.execute("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_bounded_concurrency(self) -> None:
        counter = {"active": 0, "max_seen": 0}

        async def tracked(data: str) -> str:
            counter["active"] += 1
            counter["max_seen"] = max(
                counter["max_seen"], counter["active"]
            )
            await asyncio.sleep(0.02)
            counter["active"] -= 1
            return data

        group: ParallelGroup[str] = ParallelGroup(
            name="bounded",
            stages=[
                PipelineStage(name=f"s{i}", execute=tracked)
                for i in range(6)
            ],
            max_concurrency=2,
        )
        results = await group.execute("test")
        assert len(results) == 6
        assert all(r.status == StageOutcome.COMPLETED for r in results)
        assert counter["max_seen"] <= 2

    @pytest.mark.asyncio
    async def test_timeout_cancels_slow_stages(self) -> None:
        """ParallelGroup with timeout marks incomplete stages."""

        async def _hang(data: str) -> str:
            await asyncio.sleep(10)
            return data  # pragma: no cover

        group: ParallelGroup[str] = ParallelGroup(
            name="timeout-test",
            stages=[
                PipelineStage(name="fast", execute=_succeed),
                PipelineStage(name="hanging", execute=_hang),
            ],
            timeout=0.1,
        )
        results = await group.execute("test")
        assert len(results) == 2
        # Fast stage should have completed before the timeout
        assert results[0].status == StageOutcome.COMPLETED
        # Hanging stage was either cancelled (still SKIPPED) or failed
        assert results[1].status in (
            StageOutcome.SKIPPED,
            StageOutcome.FAILED,
        )


# -- Citation verification integration --


class TestCitationVerification:
    def test_verify_citations_valid(self, tmp_path: Path) -> None:
        """Valid citation passes verification."""
        f = tmp_path / "main.py"
        f.write_text("line1\nline2\nline3\n")
        citations = [
            Citation(
                file_path="main.py",
                function_name=None,
                line_start=1,
                line_end=3,
                confidence=0.9,
            )
        ]
        results = verify_citations(citations, tmp_path)
        assert len(results) == 1
        assert results[0].passed

    def test_verify_citations_invalid_file(
        self, tmp_path: Path
    ) -> None:
        """Missing file fails verification."""
        citations = [
            Citation(
                file_path="missing.py",
                function_name=None,
                line_start=1,
                line_end=1,
                confidence=0.9,
            )
        ]
        results = verify_citations(citations, tmp_path)
        assert len(results) == 1
        assert not results[0].passed

    def test_analysis_result_quality_report_field(self) -> None:
        """AnalysisResult has quality_report field."""
        result = AnalysisResult(project_id="test")
        assert result.quality_report is None

        report = QualityReport(
            citations_checked=5,
            citations_valid=4,
            avg_confidence=0.85,
        )
        result.quality_report = report
        assert result.quality_report.citations_valid == 4

    def test_avg_confidence_helper(self) -> None:
        sections = [
            SectionOutput(
                title="A",
                section_name="a",
                content="",
                confidence=0.8,
            ),
            SectionOutput(
                title="B",
                section_name="b",
                content="",
                confidence=0.9,
            ),
        ]
        assert _avg_confidence(sections) == pytest.approx(0.85)

    def test_avg_confidence_empty(self) -> None:
        assert _avg_confidence([]) == 0.0


class TestPipelineContext:
    def test_defaults(self) -> None:
        """Context has sensible defaults for optional fields."""
        ctx = PipelineContext(
            project_id="p1",
            repo_path=Path("/tmp/repo"),
            settings=Settings(),
        )
        assert ctx.branch == "main"
        assert ctx.repo is None
        assert ctx.lang_map is None
        assert ctx.chunks is None
        assert ctx.static is None
        assert ctx.llm is None
        assert ctx.model is None
        assert ctx.sections == []
        assert ctx.dispatcher is None

    def test_mutable(self) -> None:
        """Context fields are mutable (not frozen)."""
        ctx = PipelineContext(
            project_id="p1",
            repo_path=Path("/tmp/repo"),
            settings=Settings(),
        )
        ctx.branch = "develop"
        assert ctx.branch == "develop"


class TestStageLabels:
    def test_all_stage_names_have_labels(self) -> None:
        """Every stage name used in the pipeline must have a label."""
        expected_stages = {
            "ingestion_resolve",
            "ingestion_detect",
            "ingestion_chunk",
            "static_analysis",
            "llm_analysis",
            "dual_analysis",
            "quality",
            "intelligence_model",
            "section_generation",
            "citation_verification",
            "persistence",
        }
        for name in expected_stages:
            assert name in STAGE_LABELS, (
                f"Stage '{name}' missing from STAGE_LABELS"
            )
        assert set(STAGE_LABELS.keys()) == expected_stages, (
            f"STAGE_LABELS has extra keys:"
            f" {set(STAGE_LABELS.keys()) - expected_stages}"
        )

    def test_stage_event_label_property(self) -> None:
        """StageEvent.label resolves from STAGE_LABELS."""
        from artifactor.constants import StageProgress
        from artifactor.services.analysis_service import (
            StageEvent,
        )

        event = StageEvent(
            name="ingestion_resolve",
            status=StageProgress.RUNNING,
        )
        assert event.label == "Scanning codebase"

    def test_stage_event_label_missing_raises(self) -> None:
        """StageEvent.label raises KeyError for unknown names."""
        from artifactor.constants import StageProgress
        from artifactor.services.analysis_service import (
            StageEvent,
        )

        event = StageEvent(
            name="unknown_stage",
            status=StageProgress.RUNNING,
        )
        with pytest.raises(KeyError):
            _ = event.label
