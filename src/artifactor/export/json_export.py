"""JSON export — structured envelope."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from artifactor.outputs.base import SectionOutput


def export_json(
    sections: list[SectionOutput],
    project_id: str,
) -> str:
    """Export sections as structured JSON."""
    payload: dict[str, Any] = {
        "project_id": project_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "section_count": len(sections),
        "sections": [
            _section_to_dict(s) for s in sections
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def export_single_section_json(
    section: SectionOutput,
) -> str:
    """Export a single section as JSON."""
    return json.dumps(
        _section_to_dict(section),
        indent=2,
        ensure_ascii=False,
    )


def _section_to_dict(
    section: SectionOutput,
) -> dict[str, Any]:
    """Convert a SectionOutput to a JSON-serializable dict."""
    return {
        "title": section.title,
        "section_name": section.section_name,
        "content": section.content,
        "confidence": section.confidence,
        "citation_count": len(section.citations),
        "citations": [
            {
                "file_path": c.file_path,
                "function_name": c.function_name,
                "line_start": c.line_start,
                "line_end": c.line_end,
                "confidence": c.confidence,
            }
            for c in section.citations
        ],
    }
