"""Pre-render Mermaid code blocks to inline SVG for PDF export."""

from __future__ import annotations

import asyncio
import base64
import html
import logging
import re
import shutil
import tempfile
from pathlib import Path

from artifactor.constants import ERROR_TRUNCATION_CHARS

logger = logging.getLogger(__name__)

# Matches <pre><code class="mermaid">...</code></pre> in HTML output
# (produced by html.py's markdown_to_html fenced code block handler)
_MERMAID_BLOCK_RE = re.compile(
    r'<pre><code class="mermaid">(.*?)</code></pre>',
    re.DOTALL,
)


def is_mmdc_available() -> bool:
    """Check if the Mermaid CLI is installed."""
    return shutil.which("mmdc") is not None


async def render_mermaid_to_svg(source: str) -> str | None:
    """Render a single Mermaid source string to SVG via mmdc.

    Returns SVG string on success, None on failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.mmd"
        output_file = Path(tmpdir) / "output.svg"
        input_file.write_text(source, encoding="utf-8")

        proc = await asyncio.create_subprocess_exec(
            "mmdc",
            "-i",
            str(input_file),
            "-o",
            str(output_file),
            "-e",
            "svg",
            "--quiet",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.warning(
                "event=mmdc_failed error=%s",
                stderr.decode()[:ERROR_TRUNCATION_CHARS],
            )
            return None

        if output_file.exists():
            return output_file.read_text(encoding="utf-8")
        return None


def _svg_to_img_tag(svg: str) -> str:
    """Convert SVG string to an inline base64 <img> tag."""
    encoded = base64.b64encode(
        svg.encode("utf-8")
    ).decode("ascii")
    return (
        f'<img src="data:image/svg+xml;base64,{encoded}" '
        f'alt="Mermaid diagram" '
        f'style="max-width:100%; height:auto; '
        f'margin:1em 0; display:block;" />'
    )


def _styled_code_fallback(source: str) -> str:
    """Render Mermaid source as a styled code block (no-mmdc fallback)."""
    escaped = html.escape(source.strip())
    return (
        '<div style="border:1px solid #E5E7EB; '
        "border-left:3px solid #D97706; "
        "background:#FFFBEB; padding:0.75em 1em; "
        'border-radius:4px; margin:1em 0;">'
        '<div style="font-size:8pt; color:#D97706; '
        'font-weight:600; margin-bottom:0.3em;">'
        "Mermaid Diagram (source)</div>"
        '<pre style="margin:0; font-size:8pt; '
        'white-space:pre-wrap;">'
        f"<code>{escaped}</code></pre></div>"
    )


async def prerender_mermaid_blocks(
    html_content: str,
) -> str:
    """Replace Mermaid code blocks in HTML with rendered SVGs.

    When mmdc is available, renders each block to SVG and inlines it.
    When mmdc is not available, replaces with styled code blocks
    that clearly label the content as a Mermaid diagram source.
    """
    blocks = list(_MERMAID_BLOCK_RE.finditer(html_content))
    if not blocks:
        return html_content

    if not is_mmdc_available():

        def _replace_with_fallback(
            match: re.Match[str],
        ) -> str:
            return _styled_code_fallback(match.group(1))

        return _MERMAID_BLOCK_RE.sub(
            _replace_with_fallback, html_content
        )

    # Render all blocks concurrently
    sources = [m.group(1) for m in blocks]
    svgs = await asyncio.gather(
        *[render_mermaid_to_svg(s) for s in sources]
    )

    # Replace in reverse order to preserve indices
    result = html_content
    for match, svg in zip(
        reversed(blocks), reversed(svgs), strict=True
    ):
        if svg:
            replacement = _svg_to_img_tag(svg)
        else:
            replacement = _styled_code_fallback(
                match.group(1)
            )
        result = (
            result[: match.start()]
            + replacement
            + result[match.end() :]
        )

    return result
