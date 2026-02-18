"""Tests for Mermaid pre-rendering."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from artifactor.export.mermaid_prerender import (
    _styled_code_fallback,
    _svg_to_img_tag,
    prerender_mermaid_blocks,
)

SAMPLE_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'

HTML_NO_MERMAID = "<p>Hello world</p>"

HTML_ONE_MERMAID = (
    "<p>Before</p>"
    '<pre><code class="mermaid">'
    "graph TD\n  A --> B"
    "</code></pre>"
    "<p>After</p>"
)

HTML_TWO_MERMAID = (
    '<pre><code class="mermaid">'
    "graph TD\n  A --> B"
    "</code></pre>"
    "<p>Middle</p>"
    '<pre><code class="mermaid">'
    "erDiagram\n  Foo ||--o{ Bar : has"
    "</code></pre>"
)


class TestMermaidPrerender:
    @pytest.mark.asyncio
    async def test_no_mermaid_blocks_passthrough(
        self,
    ) -> None:
        result = await prerender_mermaid_blocks(
            HTML_NO_MERMAID
        )
        assert result == HTML_NO_MERMAID

    @pytest.mark.asyncio
    async def test_mermaid_block_replaced_with_svg(
        self,
    ) -> None:
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
                return_value=SAMPLE_SVG,
            ),
        ):
            result = await prerender_mermaid_blocks(
                HTML_ONE_MERMAID
            )
        assert "<img" in result
        assert "data:image/svg+xml;base64," in result
        assert "<p>Before</p>" in result
        assert "<p>After</p>" in result
        assert '<code class="mermaid">' not in result

    @pytest.mark.asyncio
    async def test_mermaid_block_fallback_when_no_mmdc(
        self,
    ) -> None:
        with patch(
            "artifactor.export.mermaid_prerender"
            ".is_mmdc_available",
            return_value=False,
        ):
            result = await prerender_mermaid_blocks(
                HTML_ONE_MERMAID
            )
        assert "Mermaid Diagram (source)" in result
        assert "graph TD" in result
        assert '<code class="mermaid">' not in result

    @pytest.mark.asyncio
    async def test_mermaid_render_failure_falls_back(
        self,
    ) -> None:
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
                return_value=None,
            ),
        ):
            result = await prerender_mermaid_blocks(
                HTML_ONE_MERMAID
            )
        assert "Mermaid Diagram (source)" in result
        assert "<img" not in result

    @pytest.mark.asyncio
    async def test_multiple_blocks_rendered_concurrently(
        self,
    ) -> None:
        svg2 = '<svg xmlns="http://www.w3.org/2000/svg"><circle/></svg>'
        render_mock = AsyncMock(
            side_effect=[SAMPLE_SVG, svg2]
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
                render_mock,
            ),
        ):
            result = await prerender_mermaid_blocks(
                HTML_TWO_MERMAID
            )
        assert render_mock.call_count == 2
        # Both blocks should be replaced with img tags
        assert result.count("<img") == 2
        assert "<p>Middle</p>" in result


class TestHelpers:
    def test_svg_to_img_tag_encodes_base64(self) -> None:
        tag = _svg_to_img_tag(SAMPLE_SVG)
        assert tag.startswith("<img")
        assert "data:image/svg+xml;base64," in tag
        assert 'alt="Mermaid diagram"' in tag

    def test_styled_code_fallback_escapes_html(
        self,
    ) -> None:
        result = _styled_code_fallback(
            "<script>alert('xss')</script>"
        )
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert "Mermaid Diagram (source)" in result
