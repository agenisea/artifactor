"""Tests for Mermaid renderer."""

import asyncio

from artifactor.diagrams.renderer import (
    is_mmdc_available,
    render_mermaid,
)


class TestRenderer:
    def test_is_mmdc_available_returns_bool(self) -> None:
        result = is_mmdc_available()
        assert isinstance(result, bool)

    def test_render_graceful_degradation(self) -> None:
        """When mmdc is not available, returns raw source."""
        source = "graph TD\n    A --> B"
        result = asyncio.run(
            render_mermaid(source, "svg")
        )
        # Either rendered SVG or raw source (graceful degradation)
        assert isinstance(result, (str, bytes))
        if isinstance(result, str):
            assert "graph TD" in result or "<svg" in result
