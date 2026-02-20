"""Shared tool business logic — pure async functions.

Each function accepts only the protocol interfaces it actually uses (ISP).
No AgentDeps — callable from agent tools, MCP tools, or tests.
"""

from __future__ import annotations

from artifactor.config import Settings
from artifactor.constants import (
    CALL_GRAPH_DEFAULT_DEPTH,
    CALL_GRAPH_DEFAULT_DIRECTION,
    CALL_GRAPH_MAX_DEPTH,
    CALL_GRAPH_MIN_DEPTH,
    SectionName,
)
from artifactor.repositories.protocols import (
    DocumentRepository,
    EntityRepository,
    RelationshipRepository,
)


async def do_query_codebase(
    question: str,
    project_id: str,
    entity_repo: EntityRepository,
    document_repo: DocumentRepository,
    settings: Settings | None = None,
) -> str:
    """Search the codebase using hybrid vector + keyword search."""
    from artifactor.chat.rag_pipeline import retrieve_context

    try:
        context = await retrieve_context(
            query=question,
            project_id=project_id,
            entity_repo=entity_repo,
            document_repo=document_repo,
            settings=settings,
        )
    except Exception:
        return f"No relevant results found for: {question}"
    if not context.formatted:
        return f"No relevant results found for: {question}"
    return context.formatted


async def do_get_specification(
    section: str,
    project_id: str,
    document_repo: DocumentRepository,
) -> str:
    """Retrieve a full documentation section by name."""
    doc = await document_repo.get_section(project_id, section)
    if doc is None:
        return (
            f"Section '{section}' not yet generated "
            "for this project."
        )
    return doc.content


async def do_list_features(
    project_id: str,
    document_repo: DocumentRepository,
) -> str:
    """List all discovered features with code mappings."""
    doc = await document_repo.get_section(
        project_id, SectionName.FEATURES
    )
    if doc is None:
        return "Feature analysis not yet complete."
    return doc.content


async def do_get_data_model(
    project_id: str,
    entity_repo: EntityRepository,
    document_repo: DocumentRepository,
    entity_name: str = "",
) -> str:
    """Get entity attributes, types, and relationships."""
    if entity_name:
        entities = await entity_repo.search(
            project_id, entity_name, entity_type="table"
        )
        if not entities:
            return f"Entity '{entity_name}' not found."
        parts = [
            f"{e.name} ({e.entity_type}) at "
            f"{e.file_path}:{e.start_line}"
            for e in entities
        ]
        return "\n".join(parts)
    doc = await document_repo.get_section(
        project_id, SectionName.DATA_MODELS
    )
    if doc is None:
        return "Data model analysis not yet complete."
    return doc.content


async def do_explain_symbol(
    file_path: str,
    project_id: str,
    entity_repo: EntityRepository,
    relationship_repo: RelationshipRepository,
    symbol_name: str = "",
) -> str:
    """Explain purpose, callers, and callees for a symbol."""
    entities = await entity_repo.get_by_path(
        project_id, file_path
    )
    if not entities:
        return f"No entities found at '{file_path}'."
    if symbol_name:
        entities = [
            e for e in entities if e.name == symbol_name
        ]
        if not entities:
            return (
                f"Symbol '{symbol_name}' not found "
                f"in '{file_path}'."
            )
    callers = await relationship_repo.get_callers(
        project_id,
        file_path,
        symbol_name,
        depth=CALL_GRAPH_DEFAULT_DEPTH,
    )
    callees = await relationship_repo.get_callees(
        project_id,
        file_path,
        symbol_name,
        depth=CALL_GRAPH_DEFAULT_DEPTH,
    )
    parts = [f"Entities at {file_path}:"]
    for e in entities:
        parts.append(
            f"  - {e.name} ({e.entity_type}) "
            f"lines {e.start_line}-{e.end_line}"
        )
    if callers:
        parts.append("Callers:")
        for c in callers:
            parts.append(
                f"  - {c.source_file}:{c.source_symbol}"
            )
    if callees:
        parts.append("Callees:")
        for c in callees:
            parts.append(
                f"  - {c.target_file}:{c.target_symbol}"
            )
    return "\n".join(parts)


async def do_get_call_graph(
    file_path: str,
    symbol_name: str,
    project_id: str,
    relationship_repo: RelationshipRepository,
    direction: str = CALL_GRAPH_DEFAULT_DIRECTION,
    depth: int = CALL_GRAPH_DEFAULT_DEPTH,
) -> str:
    """Get call graph for a function or method."""
    depth = min(
        max(depth, CALL_GRAPH_MIN_DEPTH), CALL_GRAPH_MAX_DEPTH
    )
    parts: list[str] = []
    if direction in ("callers", "both"):
        callers = await relationship_repo.get_callers(
            project_id,
            file_path,
            symbol_name,
            depth=depth,
        )
        parts.append(
            f"Callers of {symbol_name} (depth={depth}):"
        )
        for c in callers:
            parts.append(
                f"  {c.source_file}:{c.source_symbol} "
                f"-> {c.target_symbol}"
            )
    if direction in ("callees", "both"):
        callees = await relationship_repo.get_callees(
            project_id,
            file_path,
            symbol_name,
            depth=depth,
        )
        parts.append(
            f"Callees of {symbol_name} (depth={depth}):"
        )
        for c in callees:
            parts.append(
                f"  {c.source_symbol} -> "
                f"{c.target_file}:{c.target_symbol}"
            )
    if not parts:
        return (
            f"No call graph data for "
            f"{file_path}:{symbol_name}."
        )
    return "\n".join(parts)


async def do_get_user_stories(
    project_id: str,
    document_repo: DocumentRepository,
    epic: str = "",
    persona: str = "",
) -> str:
    """Get user stories with acceptance criteria."""
    doc = await document_repo.get_section(
        project_id, SectionName.USER_STORIES
    )
    if doc is None:
        return "User stories not yet generated."
    content = doc.content
    if epic:
        content = f"[Filtered by epic: {epic}]\n{content}"
    if persona:
        content = (
            f"[Filtered by persona: {persona}]\n{content}"
        )
    return content


async def do_get_api_endpoints(
    project_id: str,
    entity_repo: EntityRepository,
    path_filter: str = "",
    method: str = "",
) -> str:
    """Get discovered API endpoints."""
    entities = await entity_repo.search(
        project_id,
        query=path_filter,
        entity_type="endpoint",
    )
    if method:
        entities = [
            e
            for e in entities
            if method.upper()
            in (e.signature or "").upper()
        ]
    if not entities:
        return "No API endpoints found."
    parts = ["Discovered API endpoints:"]
    for e in entities:
        sig = e.signature or "UNKNOWN"
        parts.append(
            f"  {sig} {e.name} "
            f"[{e.file_path}:{e.start_line}]"
        )
    return "\n".join(parts)


async def do_search_code_entities(
    query: str,
    project_id: str,
    entity_repo: EntityRepository,
    entity_type: str = "",
) -> str:
    """Search code entities by name or keyword."""
    entities = await entity_repo.search(
        project_id,
        query,
        entity_type=entity_type or None,
    )
    if not entities:
        return f"No entities found matching '{query}'."
    parts = [f"Found {len(entities)} entities:"]
    for e in entities:
        parts.append(
            f"  {e.name} ({e.entity_type}) at "
            f"{e.file_path}:{e.start_line}"
        )
    return "\n".join(parts)


async def do_get_security_findings(
    project_id: str,
    document_repo: DocumentRepository,
    severity: str = "",
    category: str = "",
) -> str:
    """Get security findings with affected files."""
    doc = await document_repo.get_section(
        project_id, SectionName.SECURITY_CONSIDERATIONS
    )
    if doc is None:
        return "Security analysis not yet complete."
    content = doc.content
    if severity:
        content = (
            f"[Filtered by severity: {severity}]\n"
            f"{content}"
        )
    if category:
        content = (
            f"[Filtered by category: {category}]\n"
            f"{content}"
        )
    return content
