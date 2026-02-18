"""HTML export — Markdown to styled HTML."""

from __future__ import annotations

import html
import re

from artifactor.outputs.base import SectionOutput

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BULLET_RE = re.compile(r"^- (.+)$", re.MULTILINE)
_FENCED_RE = re.compile(
    r"```(\w*)\n(.*?)```", re.DOTALL
)


def export_html(
    sections: list[SectionOutput],
    project_id: str,
) -> str:
    """Export sections as a styled HTML document."""
    body_parts: list[str] = []

    for section in sections:
        body_parts.append(
            f'<section id="{html.escape(section.section_name)}">'
        )
        body_parts.append(
            markdown_to_html(section.content)
        )
        body_parts.append("</section>")

    body = "\n".join(body_parts)
    return _wrap_html(body, project_id)


def export_single_section_html(
    section: SectionOutput,
) -> str:
    """Export a single section as HTML fragment."""
    return markdown_to_html(section.content)


def markdown_to_html(md: str) -> str:
    """Minimal Markdown to HTML conversion."""
    result = html.escape(md)

    # Fenced code blocks (before other transformations)
    result = _FENCED_RE.sub(
        lambda m: (
            f'<pre><code class="{html.escape(m.group(1))}">'
            f"{m.group(2)}</code></pre>"
        ),
        result,
    )

    # Headings
    result = _HEADING_RE.sub(
        lambda m: (
            f"<h{len(m.group(1))}>"
            f"{m.group(2)}"
            f"</h{len(m.group(1))}>"
        ),
        result,
    )

    # Bold
    result = _BOLD_RE.sub(r"<strong>\1</strong>", result)

    # Inline code
    result = _CODE_RE.sub(r"<code>\1</code>", result)

    # Links
    result = _LINK_RE.sub(r'<a href="\2">\1</a>', result)

    # Bullet lists
    result = _BULLET_RE.sub(r"<li>\1</li>", result)

    # Tables (basic: pipe-delimited)
    lines = result.split("\n")
    in_table = False
    out_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if "---" in stripped:
                continue  # skip separator row
            cells = [
                c.strip()
                for c in stripped.strip("|").split("|")
            ]
            tag = "th" if not in_table else "td"
            row = "".join(
                f"<{tag}>{c}</{tag}>" for c in cells
            )
            if not in_table:
                out_lines.append("<table><tr>")
                in_table = True
            else:
                out_lines.append("<tr>")
            out_lines.append(row)
            out_lines.append("</tr>")
        else:
            if in_table:
                out_lines.append("</table>")
                in_table = False
            out_lines.append(line)
    if in_table:
        out_lines.append("</table>")

    return "\n".join(out_lines)


def _wrap_html(body: str, project_id: str) -> str:
    """Wrap body in a full HTML document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Artifactor — {html.escape(project_id)}</title>
<style>
body {{
  font-family: system-ui, sans-serif;
  max-width: 900px; margin: 2em auto;
  padding: 0 1em; line-height: 1.6;
}}
code {{ background: #f4f4f4; padding: 0.2em 0.4em; border-radius: 3px; }}
pre {{ background: #f4f4f4; padding: 1em; overflow-x: auto; border-radius: 6px; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
th, td {{ border: 1px solid #ddd; padding: 0.5em; text-align: left; }}
th {{ background: #f8f8f8; }}
section {{ margin-bottom: 2em; }}
</style>
</head>
<body>
{body}
</body>
</html>"""
