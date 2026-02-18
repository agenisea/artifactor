"""Tests for export module."""

import json

from artifactor.export import export_section
from artifactor.export.html import export_html, export_single_section_html
from artifactor.export.json_export import (
    export_json,
    export_single_section_json,
)
from artifactor.export.markdown import (
    export_markdown,
    export_single_section,
)
from artifactor.intelligence.value_objects import Citation
from artifactor.outputs.base import SectionOutput


def _make_sections() -> list[SectionOutput]:
    return [
        SectionOutput(
            title="Overview",
            section_name="executive_overview",
            content="# Overview\n\nThis is a test.",
            confidence=0.9,
            citations=(
                Citation(
                    file_path="main.py",
                    function_name="greet",
                    line_start=1,
                    line_end=10,
                    confidence=0.9,
                ),
            ),
        ),
        SectionOutput(
            title="Features",
            section_name="features",
            content="# Features\n\n- Feature A\n- Feature B",
            confidence=0.85,
        ),
    ]


class TestMarkdownExport:
    def test_export_markdown_has_toc(self) -> None:
        sections = _make_sections()
        result = export_markdown(sections, "proj-1")
        assert "Table of Contents" in result
        assert "[Overview]" in result
        assert "[Features]" in result

    def test_export_markdown_has_metadata(self) -> None:
        sections = _make_sections()
        result = export_markdown(sections, "proj-1")
        assert "project: proj-1" in result
        assert "sections: 2" in result

    def test_export_single_section(self) -> None:
        section = _make_sections()[0]
        result = export_single_section(section)
        assert result == section.content


class TestHTMLExport:
    def test_export_html_full_document(self) -> None:
        sections = _make_sections()
        result = export_html(sections, "proj-1")
        assert "<!DOCTYPE html>" in result
        assert "Artifactor" in result
        assert "executive_overview" in result

    def test_export_html_has_sections(self) -> None:
        sections = _make_sections()
        result = export_html(sections, "proj-1")
        assert "<section" in result
        assert "</section>" in result

    def test_export_single_section_html(self) -> None:
        section = _make_sections()[0]
        result = export_single_section_html(section)
        assert "<h1>" in result or "Overview" in result


class TestJSONExport:
    def test_export_json_valid(self) -> None:
        sections = _make_sections()
        result = export_json(sections, "proj-1")
        data = json.loads(result)
        assert data["project_id"] == "proj-1"
        assert data["section_count"] == 2
        assert len(data["sections"]) == 2

    def test_export_json_section_structure(self) -> None:
        sections = _make_sections()
        result = export_json(sections, "proj-1")
        data = json.loads(result)
        first = data["sections"][0]
        assert first["title"] == "Overview"
        assert first["section_name"] == "executive_overview"
        assert first["confidence"] == 0.9
        assert first["citation_count"] == 1
        assert len(first["citations"]) == 1

    def test_export_single_section_json(self) -> None:
        section = _make_sections()[0]
        result = export_single_section_json(section)
        data = json.loads(result)
        assert data["title"] == "Overview"


class TestExportDispatcher:
    def test_dispatch_markdown(self) -> None:
        section = _make_sections()[0]
        result = export_section(section, "markdown")
        assert result == section.content

    def test_dispatch_html(self) -> None:
        section = _make_sections()[0]
        result = export_section(section, "html")
        assert isinstance(result, str)

    def test_dispatch_json(self) -> None:
        section = _make_sections()[0]
        result = export_section(section, "json")
        data = json.loads(result)
        assert data["title"] == "Overview"

    def test_dispatch_invalid_format(self) -> None:
        section = _make_sections()[0]
        try:
            export_section(section, "xml")
            msg = "Should have raised ValueError"
            raise AssertionError(msg)
        except ValueError:
            pass
