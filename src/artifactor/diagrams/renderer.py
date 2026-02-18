"""Mermaid rendering via mmdc CLI."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Literal


async def render_mermaid(
    source: str,
    output_format: Literal["svg", "png", "pdf"] = "svg",
    output_path: Path | None = None,
) -> str | bytes:
    """Render Mermaid syntax to SVG/PNG/PDF via mmdc.

    Returns the rendered content. If mmdc is not available,
    returns the raw Mermaid source text (graceful degradation).
    """
    if not shutil.which("mmdc"):
        return source  # graceful degradation

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.mmd"
        out_file = (
            output_path
            or Path(tmpdir) / f"output.{output_format}"
        )
        input_file.write_text(source, encoding="utf-8")

        proc = await asyncio.create_subprocess_exec(
            "mmdc",
            "-i",
            str(input_file),
            "-o",
            str(out_file),
            "-e",
            output_format,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        if proc.returncode != 0:
            # Graceful degradation: return raw source
            return source

        if output_format == "svg":
            return out_file.read_text(encoding="utf-8")
        return out_file.read_bytes()


def is_mmdc_available() -> bool:
    """Check if the Mermaid CLI (mmdc) is installed."""
    return shutil.which("mmdc") is not None
