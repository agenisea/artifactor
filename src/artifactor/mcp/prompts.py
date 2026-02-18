"""MCP prompt definitions: 5 prompts for common workflows."""

# pyright: reportUnusedFunction=false
# All functions are registered via @mcp.prompt decorator

from __future__ import annotations

from fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register all 5 MCP prompts."""

    @mcp.prompt()
    async def explain_repo(
        project_id: str,
    ) -> str:
        """Generate a project briefing: overview + architecture + features."""
        overview = await _get_section(
            project_id, "executive_overview"
        )
        architecture = await _get_section(
            project_id, "system_overview"
        )
        features = await _get_section(
            project_id, "features"
        )
        return (
            f"# Project Briefing\n\n"
            f"## Executive Overview\n{overview}\n\n"
            f"## Architecture\n{architecture}\n\n"
            f"## Key Features\n{features}"
        )

    @mcp.prompt()
    async def review_code(
        file_path: str,
        project_id: str = "",
    ) -> str:
        """Code review context with business rules and security."""
        security = await _get_section(
            project_id, "security_considerations"
        )
        system = await _get_section(
            project_id, "system_overview"
        )
        return (
            f"# Code Review Context for {file_path}\n\n"
            f"## System Overview\n{system}\n\n"
            f"## Security Considerations\n{security}\n\n"
            f"Please review the code at `{file_path}` "
            f"using the context above."
        )

    @mcp.prompt()
    async def write_tests(
        file_path: str,
        symbol_name: str = "",
        project_id: str = "",
    ) -> str:
        """Generate BDD test specifications from user stories."""
        stories = await _get_section(
            project_id, "user_stories"
        )
        target = file_path
        if symbol_name:
            target = f"{file_path}:{symbol_name}"
        return (
            f"# Test Specification for {target}\n\n"
            f"## User Stories\n{stories}\n\n"
            f"Write BDD-style test cases for "
            f"`{target}` based on the user stories "
            f"and acceptance criteria above."
        )

    @mcp.prompt()
    async def fix_bug(
        bug_description: str,
        project_id: str = "",
    ) -> str:
        """Assemble context for bug fixing."""
        system = await _get_section(
            project_id, "system_overview"
        )
        data_models = await _get_section(
            project_id, "data_models"
        )
        return (
            f"# Bug Fix Context\n\n"
            f"## Bug Description\n{bug_description}\n\n"
            f"## System Overview\n{system}\n\n"
            f"## Data Models\n{data_models}\n\n"
            f"Analyze the bug and suggest a fix "
            f"using the context above."
        )

    @mcp.prompt()
    async def migration_plan(
        target_description: str,
        project_id: str = "",
    ) -> str:
        """Generate a migration plan with risk analysis."""
        system = await _get_section(
            project_id, "system_overview"
        )
        features = await _get_section(
            project_id, "features"
        )
        security = await _get_section(
            project_id, "security_considerations"
        )
        return (
            f"# Migration Plan\n\n"
            f"## Target\n{target_description}\n\n"
            f"## Current System\n{system}\n\n"
            f"## Features to Preserve\n{features}\n\n"
            f"## Security Constraints\n{security}\n\n"
            f"Create a migration plan with ordering, "
            f"risk areas, and preserved rules."
        )


async def _get_section(
    project_id: str, section_name: str
) -> str:
    """Get a section's content, or a placeholder."""
    from artifactor.mcp.server import (
        get_session_factory,
    )
    from artifactor.repositories.document_repo import (
        SqlDocumentRepository,
    )

    factory = get_session_factory()
    async with factory() as session:
        repo = SqlDocumentRepository(session)
        doc = await repo.get_section(
            project_id, section_name
        )
    if doc is None:
        return f"*{section_name} not yet generated.*"
    return doc.content
