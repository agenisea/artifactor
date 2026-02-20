"""Chat route — SSE streaming via agent.iter()."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic_ai import Agent
from pydantic_ai.messages import ToolCallPart
from sse_starlette.sse import EventSourceResponse

from artifactor.agent.agent import create_agent
from artifactor.agent.deps import AgentDeps
from artifactor.agent.router import ChatIntent, classify_intent
from artifactor.agent.schemas import AgentResponse
from artifactor.agent.specialists import agent_for_intent
from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import ChatRequest
from artifactor.chat.rag_pipeline import retrieve_context
from artifactor.config import TIMEOUTS
from artifactor.constants import (
    ERROR_TRUNCATION_CHARS,
    ID_HEX_LENGTH,
    SSEEvent,
)
from artifactor.logger import AgentLogger
from artifactor.resilience.errors import ErrorClass, classify_error

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["chat"]
)

# ── Tool status templates for human-friendly SSE messages ───

TOOL_STATUS_TEMPLATES: dict[str, str] = {
    "query_codebase": "Searching codebase for: {question}...",
    "get_specification": "Retrieving {section} specification...",
    "list_features": "Loading discovered features...",
    "get_data_model": "Looking up data model...",
    "explain_symbol": "Explaining {symbol_name} in {file_path}...",
    "get_call_graph": "Tracing call graph for {symbol_name}...",
    "get_user_stories": "Loading user stories...",
    "get_api_endpoints": "Searching API endpoints...",
    "search_code_entities": "Searching entities: {query}...",
    "get_security_findings": "Checking security findings...",
}


def _tool_status_message(
    tool_name: str, args: str | dict[str, Any] | None
) -> str:
    """Return a human-friendly status message for a tool call."""
    template = TOOL_STATUS_TEMPLATES.get(tool_name)
    if not template or not args:
        return f"Running {tool_name}..."
    fmt_args: dict[str, Any] = {}
    if isinstance(args, dict):
        fmt_args = args
    else:
        try:
            parsed: dict[str, Any] = json.loads(args)  # type: ignore[assignment]
            fmt_args = parsed
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    if not fmt_args:
        return f"Running {tool_name}..."
    try:
        return template.format(**fmt_args)
    except KeyError:
        return f"Running {tool_name}..."


# ── Streaming helper (reusable for specialist + fallback) ───


async def _stream_agent_run(
    agent: Agent[AgentDeps, AgentResponse],
    user_prompt: str,
    deps: AgentDeps,
    request_id: str,
    conversation_id: str,
    metadata: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, str]]:
    """Yield SSE events from an agent run.

    Reused for both the specialist attempt and the general fallback.
    Contains the agent.iter() loop, tool call event extraction,
    model name tracking, and the final complete event.

    Args:
        agent: The pydantic-ai agent to run.
        user_prompt: The user's message (with RAG context prepended).
        deps: Agent dependencies (repos, logger, etc.).
        request_id: Unique request identifier for SSE correlation.
        conversation_id: Conversation thread ID for frontend threading.
            Passed through to the complete event unchanged.
        metadata: Optional mutable dict — caller passes {} to collect
            model_name, tools_called, tokens after the generator completes.
    """
    model_name = "unknown"
    tools_called: list[str] = []

    async with agent.iter(user_prompt, deps=deps) as agent_run:
        async for node in agent_run:
            if Agent.is_call_tools_node(node):
                resp = node.model_response
                if resp.model_name:
                    model_name = resp.model_name
                for part in resp.parts:
                    if isinstance(part, ToolCallPart):
                        tools_called.append(part.tool_name)
                        args = (
                            part.args
                            if isinstance(
                                part.args, (dict, str)
                            )
                            else None
                        )
                        yield {
                            "event": SSEEvent.TOOL_CALL,
                            "data": json.dumps({
                                "tool": part.tool_name,
                                "message": _tool_status_message(
                                    part.tool_name, args
                                ),
                                "request_id": request_id,
                            }),
                        }

    if agent_run.result is None:
        raise RuntimeError("Agent returned no result")

    agent_response = agent_run.result.output
    usage = agent_run.result.usage()

    # Populate metadata for caller logging
    if metadata is not None:
        metadata["model_name"] = model_name
        metadata["tools_called"] = tools_called
        metadata["tokens"] = (
            (usage.input_tokens or 0)
            + (usage.output_tokens or 0)
        )

    yield {
        "event": SSEEvent.COMPLETE,
        "data": json.dumps({
            "message": agent_response.message,
            "citations": [
                c.model_dump()
                for c in agent_response.citations
            ],
            "confidence": (
                agent_response.confidence.model_dump()
                if agent_response.confidence
                else None
            ),
            "tools_used": tools_called
            or agent_response.tools_used,
            "conversation_id": conversation_id,
            "request_id": request_id,
            "model": model_name,
            "tokens": (usage.input_tokens or 0)
            + (usage.output_tokens or 0),
        }),
    }


# ── Extracted helpers ─────────────────────────────────


async def _build_rag_prompt(
    message: str,
    project_id: str,
    repos: Repos,
    settings: Any,
) -> str:
    """Retrieve RAG context and build the augmented user prompt.

    Returns the original message if retrieval fails.
    """
    try:
        context = await retrieve_context(
            query=message,
            project_id=project_id,
            entity_repo=repos.entity,
            document_repo=repos.document,
            settings=settings,
        )
    except Exception:
        logger.warning(
            "event=rag_retrieval_failed", exc_info=True
        )
        return message

    if context and context.formatted:
        return (
            f"Context:\n{context.formatted}\n\n"
            f"Question: {message}"
        )
    return message


def _error_to_sse_event(
    exc: Exception,
    request_id: str,
) -> dict[str, str]:
    """Map an exception to a sanitized SSE error event."""
    error_class = classify_error(exc)
    logger.warning(
        "event=chat_error class=%s"
        " retryable=%s error=%s"
        " request_id=%s",
        error_class.value,
        error_class
        in (
            ErrorClass.TRANSIENT,
            ErrorClass.SERVER,
            ErrorClass.TIMEOUT,
        ),
        str(exc)[:ERROR_TRUNCATION_CHARS],
        request_id,
    )
    if error_class == ErrorClass.TIMEOUT:
        msg = (
            "Chat response timed out."
            " Please try a simpler question."
        )
        cls = "timeout"
    elif error_class == ErrorClass.CLIENT:
        msg = (
            "Chat request failed"
            " due to a configuration error."
        )
        cls = "client"
    else:
        msg = "Chat request failed. Please try again."
        cls = error_class.value

    return {
        "event": SSEEvent.ERROR,
        "data": json.dumps({
            "error": msg,
            "request_id": request_id,
            "error_class": cls,
        }),
    }


# ── Main chat event stream ────────────────────────────


async def _chat_event_stream(
    request: Request,
    project_id: str,
    body: ChatRequest,
    repos: Repos,
) -> AsyncIterator[dict[str, str]]:
    """Async generator that yields SSE events for a chat turn.

    Uses intent routing to dispatch to specialized agents with
    focused prompts and tool subsets. Falls back to the general
    agent if a specialist fails.
    """
    settings = request.app.state.settings
    request_id = uuid.uuid4().hex[:ID_HEX_LENGTH]

    agent_logger: AgentLogger = request.app.state.logger

    deps = AgentDeps(
        project_repo=repos.project,
        document_repo=repos.document,
        entity_repo=repos.entity,
        relationship_repo=repos.relationship,
        conversation_repo=repos.conversation,
        logger=agent_logger,
        request_id=request_id,
        project_id=project_id,
    )

    # 1. Yield thinking event
    yield {
        "event": SSEEvent.THINKING,
        "data": json.dumps(
            {
                "status": "Searching codebase...",
                "request_id": request_id,
            }
        ),
    }

    # 2. Retrieve RAG context + build prompt
    user_prompt = await _build_rag_prompt(
        body.message, project_id, repos, settings
    )

    # 3. Classify intent and select agent
    agent_model = getattr(
        request.app.state, "agent_model", None
    )
    intent = classify_intent(body.message)
    agent = agent_for_intent(intent, agent_model)
    conversation_id = body.conversation_id or request_id

    yield {
        "event": SSEEvent.THINKING,
        "data": json.dumps({
            "status": f"Routing to {intent.value} agent...",
            "request_id": request_id,
            "intent": intent.value,
        }),
    }

    start = time.monotonic()

    try:
        # Single timeout wraps BOTH specialist + fallback
        async with asyncio.timeout(
            TIMEOUTS["chat_agent"]
        ):
            run_meta: dict[str, Any] = {}
            try:
                async for event in _stream_agent_run(
                    agent,
                    user_prompt,
                    deps,
                    request_id,
                    conversation_id,
                    run_meta,
                ):
                    yield event
            except Exception as exc:
                if intent != ChatIntent.GENERAL:
                    logger.warning(
                        "event=specialist_fallback"
                        " intent=%s error=%s",
                        intent.value,
                        str(exc)[
                            :ERROR_TRUNCATION_CHARS
                        ],
                    )
                    yield {
                        "event": SSEEvent.THINKING,
                        "data": json.dumps({
                            "status": "Retrying with"
                            " general agent...",
                            "request_id": request_id,
                            "intent": ChatIntent.GENERAL,
                        }),
                    }
                    general_agent = create_agent(
                        model=agent_model
                    )
                    run_meta = {}
                    async for event in _stream_agent_run(
                        general_agent,
                        user_prompt,
                        deps,
                        request_id,
                        conversation_id,
                        run_meta,
                    ):
                        yield event
                else:
                    raise

        # SUCCESS PATH ONLY — log_request() not called on errors
        duration_ms = int(
            (time.monotonic() - start) * 1000
        )
        agent_logger.log_request(
            request_id=request_id,
            query=body.message,
            model=run_meta.get("model_name", "unknown"),
            tokens=run_meta.get("tokens", 0),
            tools_called=run_meta.get(
                "tools_called", []
            ),
            duration_ms=duration_ms,
            intent=intent.value,
        )

    except Exception as exc:
        yield _error_to_sse_event(exc, request_id)


@router.post("/chat")
async def chat(
    request: Request,
    project_id: str,
    body: ChatRequest,
    repos: Repos = Depends(get_repos),
) -> EventSourceResponse:
    """RAG-backed chat with SSE streaming."""
    return EventSourceResponse(
        _chat_event_stream(
            request, project_id, body, repos
        ),
        sep="\n",
    )
