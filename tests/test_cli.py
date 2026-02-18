"""Tests for CLI argument parsing and output writing."""

from __future__ import annotations

import json
from pathlib import Path

from artifactor.cli import _build_parser, _write_output
from artifactor.outputs.base import SectionOutput


class TestArgParser:
    def test_version_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["--version"])
        assert args.version is True

    def test_analyze_defaults(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["analyze", "/tmp/repo"])
        assert args.command == "analyze"
        assert args.repo_path == "/tmp/repo"
        assert args.branch == "main"
        assert args.output_dir == "artifactor-output"
        assert args.format == "markdown"
        assert args.sections is None
        assert args.verbose is False

    def test_analyze_with_options(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            [
                "analyze",
                "/tmp/repo",
                "--branch",
                "develop",
                "--output-dir",
                "./docs",
                "--format",
                "json",
                "--sections",
                "features,personas",
                "--verbose",
            ]
        )
        assert args.branch == "develop"
        assert args.output_dir == "./docs"
        assert args.format == "json"
        assert args.sections == "features,personas"
        assert args.verbose is True

    def test_no_command_prints_help(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.command is None


class TestWriteOutput:
    def test_creates_directory_and_files(
        self, tmp_path: Path
    ) -> None:
        sections = [
            SectionOutput(
                title="Overview",
                section_name="executive_overview",
                content="# Overview\nContent.",
                confidence=0.9,
            ),
            SectionOutput(
                title="Features",
                section_name="features",
                content="# Features\n- A\n- B",
                confidence=0.85,
            ),
        ]
        output_dir = tmp_path / "output"
        _write_output(sections, "proj-1", output_dir, "markdown")

        assert output_dir.exists()
        assert (output_dir / "sections").is_dir()
        assert (
            output_dir / "sections" / "01-executive_overview.md"
        ).exists()
        assert (
            output_dir / "sections" / "02-features.md"
        ).exists()
        assert (output_dir / "README.md").exists()
        assert (output_dir / "metadata.json").exists()

    def test_metadata_json(self, tmp_path: Path) -> None:
        sections = [
            SectionOutput(
                title="Overview",
                section_name="executive_overview",
                content="# Overview",
                confidence=0.9,
            ),
        ]
        output_dir = tmp_path / "out"
        _write_output(sections, "proj-1", output_dir, "markdown")

        metadata = json.loads(
            (output_dir / "metadata.json").read_text()
        )
        assert metadata["project_id"] == "proj-1"
        assert metadata["section_count"] == 1
        assert metadata["format"] == "markdown"
        assert metadata["sections"][0]["name"] == "executive_overview"

    def test_json_format_output(
        self, tmp_path: Path
    ) -> None:
        sections = [
            SectionOutput(
                title="Overview",
                section_name="executive_overview",
                content="# Overview",
                confidence=0.9,
            ),
        ]
        output_dir = tmp_path / "json_out"
        _write_output(sections, "proj-1", output_dir, "json")

        assert (
            output_dir / "sections" / "01-executive_overview.json"
        ).exists()
        assert (output_dir / "analysis.json").exists()
        data = json.loads(
            (output_dir / "analysis.json").read_text()
        )
        assert data["project_id"] == "proj-1"

    def test_html_format_output(
        self, tmp_path: Path
    ) -> None:
        sections = [
            SectionOutput(
                title="Overview",
                section_name="executive_overview",
                content="# Overview",
                confidence=0.9,
            ),
        ]
        output_dir = tmp_path / "html_out"
        _write_output(sections, "proj-1", output_dir, "html")

        html_file = (
            output_dir
            / "sections"
            / "01-executive_overview.html"
        )
        assert html_file.exists()
        content = html_file.read_text()
        assert "Overview" in content


class TestAnalysisService:
    def test_stage_status_defaults(self) -> None:
        from artifactor.services.analysis_service import (
            StageStatus,
        )

        status = StageStatus(name="test", ok=True)
        assert status.duration_ms == 0.0
        assert status.error is None

    def test_analysis_result_defaults(self) -> None:
        from artifactor.services.analysis_service import (
            AnalysisResult,
        )

        result = AnalysisResult(project_id="test")
        assert result.stages == []
        assert result.sections == []
        assert result.model is None
        assert result.total_duration_ms == 0.0
