"""Export module — multi-format document export."""

from collections.abc import Callable

from artifactor.constants import ExportFormat
from artifactor.export.html import export_html, export_single_section_html
from artifactor.export.json_export import (
    export_json,
    export_single_section_json,
)
from artifactor.export.markdown import (
    export_markdown,
    export_single_section,
)
from artifactor.export.pdf import export_pdf, export_single_section_pdf
from artifactor.outputs.base import SectionOutput

__all__ = [
    "export_html",
    "export_json",
    "export_markdown",
    "export_pdf",
    "export_section",
    "export_single_section",
    "export_single_section_html",
    "export_single_section_json",
    "export_single_section_pdf",
]

_SECTION_EXPORTERS: dict[
    str, Callable[[SectionOutput], str | bytes]
] = {
    ExportFormat.MARKDOWN: export_single_section,
    ExportFormat.HTML: export_single_section_html,
    ExportFormat.JSON: export_single_section_json,
    ExportFormat.PDF: export_single_section_pdf,
}


def export_section(
    section: SectionOutput,
    fmt: str = "markdown",
) -> str | bytes:
    """Dispatch export for a single section by format string.

    Returns ``str`` for text formats, ``bytes`` for binary (pdf).
    """
    exporter = _SECTION_EXPORTERS.get(fmt)
    if exporter is None:
        valid = ", ".join(_SECTION_EXPORTERS)
        msg = f"Unsupported format: {fmt}. Use: {valid}"
        raise ValueError(msg)
    return exporter(section)
