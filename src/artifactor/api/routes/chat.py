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


async def _chat_event_stream(
    request: Request,
    project_id: str,
    body: ChatRequest,
    repos: Repos,
) -> AsyncIterator[dict[str, str]]:
    """Async generator that yields SSE events for a chat turn.

    Uses agent.iter() for real-time tool call streaming with
    human-friendly status messages and model name tracking.
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

    # 2. Retrieve RAG context
    try:
        context = await retrieve_context(
            query=body.message,
            project_id=project_id,
            entity_repo=repos.entity,
            document_repo=repos.document,
            settings=settings,
        )
    except Exception:
        logger.warning("event=rag_retrieval_failed", exc_info=True)
        context = None

    # 3. Build prompt with context
    user_prompt = body.message
    if context and context.formatted:
        user_prompt = (
            f"Context:\n{context.formatted}\n\n"
            f"Question: {body.message}"
        )

    # 4. Run agent with iter() for streaming
    yield {
        "event": SSEEvent.THINKING,
        "data": json.dumps(
            {
                "status": "Generating response...",
                "request_id": request_id,
            }
        ),
    }

    try:
        agent_model = getattr(
            request.app.state, "agent_model", None
        )
        agent = create_agent(model=agent_model)

        model_name = "unknown"
        tools_called: list[str] = []
        start = time.monotonic()

        async with asyncio.timeout(
            TIMEOUTS["chat_agent"]
        ):
            async with agent.iter(
                user_prompt, deps=deps
            ) as agent_run:
                async for node in agent_run:
                    if Agent.is_call_tools_node(node):
                        resp = node.model_response
                        if resp.model_name:
                            model_name = resp.model_name
                        for part in resp.parts:
                            if isinstance(
                                part, ToolCallPart
                            ):
                                tools_called.append(
                                    part.tool_name
                                )
                                args = (
                                    part.args
                                    if isinstance(
                                        part.args,
                                        (dict, str),
                                    )
                                    else None
                                )
                                msg = (
                                    _tool_status_message(
                                        part.tool_name,
                                        args,
                                    )
                                )
                                yield {
                                    "event": SSEEvent.TOOL_CALL,
                                    "data": json.dumps(
                                        {
                                            "tool": part.tool_name,
                                            "message": msg,
                                            "request_id": request_id,
                                        }
                                    ),
                                }

        duration_ms = int(
            (time.monotonic() - start) * 1000
        )

        if agent_run.result is None:
            raise RuntimeError("Agent returned no result")
        agent_response = agent_run.result.output

        # Log the completed request
        usage = agent_run.result.usage()
        agent_logger.log_request(
            request_id=request_id,
            query=body.message,
            model=model_name,
            tokens=(usage.input_tokens or 0)
            + (usage.output_tokens or 0),
            tools_called=tools_called,
            duration_ms=duration_ms,
        )

        # 5. Yield complete event
        response_data: dict[str, Any] = {
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
            "conversation_id": body.conversation_id
            or request_id,
            "request_id": request_id,
            "model": model_name,
        }
        yield {
            "event": SSEEvent.COMPLETE,
            "data": json.dumps(response_data),
        }

    except Exception as exc:
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
            yield {
                "event": SSEEvent.ERROR,
                "data": json.dumps(
                    {
                        "error": "Chat response timed"
                        " out. Please try a simpler"
                        " question.",
                        "request_id": request_id,
                        "error_class": "timeout",
                    }
                ),
            }
        elif error_class == ErrorClass.CLIENT:
            yield {
                "event": SSEEvent.ERROR,
                "data": json.dumps(
                    {
                        "error": "Chat request failed"
                        " due to a configuration"
                        " error.",
                        "request_id": request_id,
                        "error_class": "client",
                    }
                ),
            }
        else:
            yield {
                "event": SSEEvent.ERROR,
                "data": json.dumps(
                    {
                        "error": "Chat request failed."
                        " Please try again.",
                        "request_id": request_id,
                        "error_class": error_class.value,
                    }
                ),
            }


@router.post("/chat")
async def chat(
    request: Request,
    project_id: str,
    body: ChatRequest,
    repos: Repos = Depends(get_repos),
) -> EventSourceResponse:
    """RAG-backed chat with SSE streaming."""
    return EventSourceResponse(
        _chat_event_stream(request, project_id, body, repos),
        sep="\n",
    )
