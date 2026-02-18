"""Markdown export — pass-through with TOC and metadata."""

from __future__ import annotations

from datetime import UTC, datetime

from artifactor.outputs.base import SectionOutput


def export_markdown(
    sections: list[SectionOutput],
    project_id: str,
) -> str:
    """Export sections as a single Markdown document with TOC."""
    parts: list[str] = []

    # Metadata header
    parts.append("---")
    parts.append(f"project: {project_id}")
    parts.append(
        f"generated: {datetime.now(UTC).isoformat()}"
    )
    parts.append(
        f"sections: {len(sections)}"
    )
    parts.append("---\n")

    # Table of contents
    parts.append("# Table of Contents\n")
    for i, section in enumerate(sections, 1):
        anchor = section.section_name.replace("_", "-")
        parts.append(
            f"{i}. [{section.title}](#{anchor})"
        )
    parts.append("")

    # Section content
    for section in sections:
        parts.append(f'<a id="{section.section_name.replace("_", "-")}"></a>\n')
        parts.append(section.content)
        parts.append("")

    return "\n".join(parts)


def export_single_section(section: SectionOutput) -> str:
    """Export a single section as Markdown."""
    return section.content
