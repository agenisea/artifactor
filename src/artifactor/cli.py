"""CLI entry point — ``artifactor analyze`` and ``artifactor mcp``."""

from __future__ import annotations

# Phase 1: Singleton logging — before any transitive litellm imports
from artifactor.logging_config import setup_logging

setup_logging()

import argparse  # noqa: E402
import asyncio  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

from artifactor import __version__  # noqa: E402
from artifactor.config import SECTION_TITLES, Settings  # noqa: E402
from artifactor.constants import StageProgress  # noqa: E402
from artifactor.logging_config import (  # noqa: E402
    cleanup_third_party_handlers,
)
from artifactor.outputs.base import SectionOutput  # noqa: E402

# Phase 2: Clear litellm's duplicate handlers after all imports
cleanup_third_party_handlers()


def main() -> None:
    """Main CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.version:
        print(f"artifactor {__version__}")
        return

    if args.command == "analyze":
        _run_analyze(args)
    elif args.command == "mcp":
        _run_mcp(args)
    else:
        parser.print_help()


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="artifactor",
        description=(
            "Code intelligence platform — "
            "turns any codebase into queryable intelligence."
        ),
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit",
    )

    sub = parser.add_subparsers(dest="command")

    analyze = sub.add_parser(
        "analyze",
        help="Analyze a repository",
    )
    analyze.add_argument(
        "repo_path",
        type=str,
        help="Path to local repository",
    )
    analyze.add_argument(
        "--branch",
        "-b",
        default="main",
        help="Git branch to analyze (default: main)",
    )
    analyze.add_argument(
        "--output-dir",
        "-o",
        default="artifactor-output",
        help="Output directory (default: artifactor-output)",
    )
    analyze.add_argument(
        "--format",
        "-f",
        choices=["markdown", "html", "json"],
        default="markdown",
        help="Export format (default: markdown)",
    )
    analyze.add_argument(
        "--sections",
        "-s",
        type=str,
        default=None,
        help=(
            "Comma-separated section names "
            "(default: all 13)"
        ),
    )
    analyze.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    mcp_parser = sub.add_parser(
        "mcp",
        help="Start MCP server",
    )
    mcp_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help=(
            "Default project ID for tools "
            "that accept project_id"
        ),
    )
    mcp_parser.add_argument(
        "--db",
        default=None,
        help=(
            "Database path override "
            "(default: from settings)"
        ),
    )
    mcp_parser.add_argument(
        "--transport",
        "-t",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    mcp_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help=(
            "Bind address for SSE transport "
            "(default: 0.0.0.0)"
        ),
    )
    mcp_parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for SSE transport (default: 8001)",
    )

    return parser


def _run_analyze(args: argparse.Namespace) -> None:
    """Execute the analyze command."""
    from artifactor.services.analysis_service import (
        StageEvent,
        run_analysis,
    )

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        print(f"Error: {repo_path} does not exist", file=sys.stderr)
        sys.exit(1)

    sections = (
        [s.strip() for s in args.sections.split(",")]
        if args.sections
        else None
    )

    # Validate section names
    if sections:
        for name in sections:
            if name not in SECTION_TITLES:
                print(
                    f"Error: unknown section '{name}'. "
                    f"Valid: {', '.join(SECTION_TITLES)}",
                    file=sys.stderr,
                )
                sys.exit(1)

    settings = Settings()
    output_dir = Path(args.output_dir)

    def on_progress(event: StageEvent) -> None:
        if args.verbose and event.status == StageProgress.RUNNING:
            print(f"  {event.message or event.name}...")

    print(f"Analyzing: {repo_path}")

    result = asyncio.run(
        run_analysis(
            repo_path=repo_path,
            settings=settings,
            sections=sections,
            branch=args.branch,
            on_progress=on_progress,
        )
    )

    # Report stage results
    ok_count = sum(1 for s in result.stages if s.ok)
    fail_count = sum(1 for s in result.stages if not s.ok)
    if args.verbose:
        for stage in result.stages:
            status = "ok" if stage.ok else "FAILED"
            print(
                f"  [{status}] {stage.name} "
                f"({stage.duration_ms:.0f}ms)"
            )
            if stage.error:
                print(f"    Error: {stage.error}")

    # Write output
    _write_output(
        result.sections,
        result.project_id,
        output_dir,
        args.format,
    )

    # Summary
    print(
        f"\nDone! {len(result.sections)} sections generated "
        f"({ok_count} stages ok, {fail_count} failed)"
    )
    print(
        f"Output: {output_dir}/ "
        f"({result.total_duration_ms:.0f}ms)"
    )


def _write_output(
    sections: list[SectionOutput],
    project_id: str,
    output_dir: Path,
    fmt: str,
) -> None:
    """Write section outputs to the output directory."""
    from artifactor.export import export_section
    from artifactor.export.json_export import export_json
    from artifactor.export.markdown import export_markdown

    output_dir.mkdir(parents=True, exist_ok=True)
    sections_dir = output_dir / "sections"
    sections_dir.mkdir(exist_ok=True)

    ext = {
        "markdown": "md", "html": "html",
        "json": "json", "pdf": "pdf",
    }.get(fmt, "md")

    # Write individual sections
    for i, section in enumerate(sections, 1):
        content = export_section(section, fmt)
        filename = f"{i:02d}-{section.section_name}.{ext}"
        if isinstance(content, bytes):
            (sections_dir / filename).write_bytes(content)
        else:
            (sections_dir / filename).write_text(
                content, encoding="utf-8"
            )

    # Write combined document
    if fmt == "pdf":
        from artifactor.export.pdf import export_pdf

        pdf_bytes = export_pdf(sections, project_id)
        (output_dir / "analysis.pdf").write_bytes(pdf_bytes)
    elif fmt == "markdown":
        combined = export_markdown(sections, project_id)
        (output_dir / "README.md").write_text(
            combined, encoding="utf-8"
        )
    elif fmt == "json":
        combined = export_json(sections, project_id)
        (output_dir / "analysis.json").write_text(
            combined, encoding="utf-8"
        )

    # Write metadata
    metadata = {
        "project_id": project_id,
        "section_count": len(sections),
        "format": fmt,
        "sections": [
            {
                "name": s.section_name,
                "title": s.title,
                "confidence": s.confidence,
            }
            for s in sections
        ],
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def _run_mcp(args: argparse.Namespace) -> None:
    """Start the MCP server over stdio."""
    # Validate --db path exists before doing anything else
    if args.db and not Path(args.db).exists():
        print(
            f"Error: database not found: {args.db}",
            file=sys.stderr,
        )
        sys.exit(1)

    settings = Settings()

    # Database URL — override or from settings
    db_url = settings.database_url
    if args.db:
        db_url = f"sqlite:///{args.db}"
    db_url = db_url.replace(
        "sqlite:///", "sqlite+aiosqlite:///"
    )

    asyncio.run(
        _setup_and_run_mcp(
            db_url,
            args.project,
            args.transport,
            args.host,
            args.port,
        )
    )


async def _setup_and_run_mcp(
    db_url: str,
    project_id: str | None,
    transport: str = "stdio",
    host: str = "0.0.0.0",
    port: int = 8001,
) -> None:
    """Initialize engine, set WAL, run MCP, dispose engine."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import (
        async_sessionmaker,
        create_async_engine,
    )

    from artifactor.mcp import configure, mcp

    engine = create_async_engine(db_url)

    # WAL mode: allow concurrent reads from the backend
    async with engine.begin() as conn:
        await conn.execute(
            text("PRAGMA journal_mode=WAL")
        )

    session_factory = async_sessionmaker(
        engine, expire_on_commit=False
    )
    configure(
        session_factory, default_project_id=project_id
    )

    try:
        if transport == "stdio":
            await mcp.run_async(transport="stdio")
        else:
            await mcp.run_async(
                transport="sse", host=host, port=port
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    main()
