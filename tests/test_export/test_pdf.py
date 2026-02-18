"""Tests for PDF export via WeasyPrint."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from artifactor.api.dependencies import (
    Repos,
    get_data_service,
    get_project_service,
    get_repos,
)
from artifactor.config import Settings
from artifactor.export import export_section
from artifactor.export.pdf import PDF_STYLESHEET, _build_pdf_html
from artifactor.intelligence.value_objects import Citation
from artifactor.logger import AgentLogger
from artifactor.main import app
from artifactor.models.document import Document
from artifactor.outputs.base import SectionOutput
from artifactor.repositories.fakes import (
    FakeConversationRepository,
    FakeDataService,
    FakeDocumentRepository,
    FakeEntityRepository,
    FakeProjectRepository,
    FakeProjectService,
    FakeRelationshipRepository,
)

try:
    from weasyprint import HTML as _HTML  # noqa: F401

    _WEASYPRINT_AVAILABLE = True
except OSError:
    _WEASYPRINT_AVAILABLE = False

weasyprint_required = pytest.mark.skipif(
    not _WEASYPRINT_AVAILABLE,
    reason="WeasyPrint system deps not available",
)


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


@pytest.fixture
async def pdf_client(tmp_path: Path):
    """Test client with seeded section data (no database)."""
    fake_project_repo = FakeProjectRepository()
    fake_doc_repo = FakeDocumentRepository()
    fake_repos = Repos(
        project=fake_project_repo,
        document=fake_doc_repo,
        entity=FakeEntityRepository(),
        relationship=FakeRelationshipRepository(),
        conversation=FakeConversationRepository(),
    )
    fake_project_service = FakeProjectService(fake_project_repo)

    # Seed a document via fake repo
    await fake_doc_repo.upsert_section(
        Document(
            project_id="test-proj",
            section_name="executive_overview",
            content="# Overview\n\nTest content for PDF.",
            confidence=0.9,
        )
    )

    app.state.settings = Settings(
        database_url="sqlite:///:memory:"
    )
    app.state.logger = AgentLogger(
        log_dir=Path(tmp_path / "logs"), level="WARNING"
    )
    app.state.project_service = fake_project_service

    app.dependency_overrides[get_repos] = lambda: fake_repos
    app.dependency_overrides[get_project_service] = (
        lambda: fake_project_service
    )
    app.dependency_overrides[get_data_service] = (
        lambda: FakeDataService()
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ── Task 74 tests ──────────────────────────────────────────


@weasyprint_required
class TestPDFExportCore:
    def test_export_pdf_returns_bytes(self) -> None:
        from artifactor.export.pdf import export_pdf

        sections = _make_sections()
        result = export_pdf(sections, "proj-1")
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_export_pdf_writes_to_file(
        self, tmp_path: Path
    ) -> None:
        from artifactor.export.pdf import export_pdf

        sections = _make_sections()
        out = tmp_path / "test.pdf"
        export_pdf(sections, "proj-1", output_path=out)
        assert out.exists()
        assert out.read_bytes()[:5] == b"%PDF-"

    def test_export_single_section_pdf(self) -> None:
        from artifactor.export.pdf import export_single_section_pdf

        section = _make_sections()[0]
        result = export_single_section_pdf(section)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"


# ── Task 75 tests ──────────────────────────────────────────


@weasyprint_required
class TestPDFBranding:
    def test_pdf_has_multiple_pages(self) -> None:
        from artifactor.export.pdf import export_pdf

        single = export_pdf(_make_sections()[:1], "proj-1")
        multi = export_pdf(_make_sections(), "proj-1")
        # Multi-section PDF should be larger than single
        assert len(multi) > len(single)

    def test_pdf_cover_page_in_html(self) -> None:
        sections = _make_sections()
        html = _build_pdf_html(sections, "my-project")
        assert 'class="cover-page"' in html
        assert "my-project" in html
        assert "Code Intelligence Report" in html

    def test_pdf_stylesheet_has_brand_colors(self) -> None:
        assert "#3730A3" in PDF_STYLESHEET
        assert "@page" in PDF_STYLESHEET
        assert "system-ui" in PDF_STYLESHEET


# ── Task 76 tests ──────────────────────────────────────────


class TestPDFDispatcher:
    @weasyprint_required
    def test_dispatcher_pdf_returns_bytes(self) -> None:
        section = _make_sections()[0]
        result = export_section(section, "pdf")
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"


class TestPDFAPIRoute:
    @weasyprint_required
    @pytest.mark.asyncio
    async def test_api_export_pdf_returns_pdf_content_type(
        self, pdf_client: AsyncClient
    ) -> None:
        resp = await pdf_client.get(
            "/api/projects/test-proj/sections"
            "/executive_overview/export?format=pdf"
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    @weasyprint_required
    @pytest.mark.asyncio
    async def test_api_export_pdf_has_content_disposition(
        self, pdf_client: AsyncClient
    ) -> None:
        resp = await pdf_client.get(
            "/api/projects/test-proj/sections"
            "/executive_overview/export?format=pdf"
        )
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "executive_overview.pdf" in cd

    def test_export_section_route_is_async(self) -> None:
        """Verify the route is async (required for to_thread)."""
        from artifactor.api.routes.sections import (
            export_section as route_fn,
        )

        assert inspect.iscoroutinefunction(route_fn)

    def test_export_pdf_function_is_sync(self) -> None:
        """Verify export_pdf is sync (must be offloaded)."""
        from artifactor.export.pdf import export_pdf

        assert not inspect.iscoroutinefunction(export_pdf)


# ── Mermaid in PDF ──────────────────────────────────────


def _make_mermaid_section() -> SectionOutput:
    return SectionOutput(
        title="Data Models",
        section_name="data_models",
        content=(
            "# Data Models\n\n"
            "```mermaid\n"
            "erDiagram\n"
            "  User ||--o{ Order : places\n"
            "```\n\n"
            "Some text after."
        ),
        confidence=0.8,
    )


class TestPDFMermaidPrerender:
    @weasyprint_required
    def test_pdf_with_mermaid_block_renders_svg(
        self,
    ) -> None:
        """When mmdc is mocked as available, Mermaid blocks
        become inline SVG <img> tags in the PDF HTML."""
        from unittest.mock import AsyncMock, patch

        fake_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<text>ER</text></svg>"
        )
        with (
            patch(
                "artifactor.export.mermaid_prerender"
                ".is_mmdc_available",
                return_value=True,
            ),
            patch(
                "artifactor.export.mermaid_prerender"
                ".render_mermaid_to_svg",
                new_callable=AsyncMock,
                return_value=fake_svg,
            ),
        ):
            from artifactor.export.pdf import export_pdf

            result = export_pdf(
                [_make_mermaid_section()], "proj-mermaid"
            )
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    @weasyprint_required
    def test_pdf_with_mermaid_no_mmdc_has_fallback(
        self,
    ) -> None:
        """When mmdc is not available, Mermaid blocks become
        styled code blocks with a source label."""
        from unittest.mock import patch

        with patch(
            "artifactor.export.mermaid_prerender"
            ".is_mmdc_available",
            return_value=False,
        ):
            from artifactor.export.pdf import export_pdf

            result = export_pdf(
                [_make_mermaid_section()], "proj-no-mmdc"
            )
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    @weasyprint_required
    def test_pdf_without_mermaid_unchanged(self) -> None:
        """Sections without Mermaid blocks produce normal PDF."""
        from artifactor.export.pdf import export_pdf

        sections = _make_sections()
        result = export_pdf(sections, "proj-plain")
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"
