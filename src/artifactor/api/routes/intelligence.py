"""Intelligence query route — RAG-backed JSON responses."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from artifactor.api.dependencies import Repos, get_repos
from artifactor.api.schemas import APIResponse
from artifactor.chat.rag_pipeline import retrieve_context
from artifactor.constants import ERROR_TRUNCATION_CHARS

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}", tags=["intelligence"]
)


class QueryRequest(BaseModel):
    """Request body for intelligence query."""

    question: str = Field(min_length=1, max_length=10_000)


@router.post("/query")
async def query_intelligence(
    request: Request,
    project_id: str,
    body: QueryRequest,
    repos: Repos = Depends(get_repos),
) -> APIResponse:
    """RAG-backed intelligence query (JSON response).

    Unlike the chat SSE route, this returns a single JSON
    response with context — no streaming, no agent iteration.
    """
    try:
        context = await retrieve_context(
            query=body.question,
            project_id=project_id,
            entity_repo=repos.entity,
            document_repo=repos.document,
            settings=request.app.state.settings,
        )
    except Exception:
        logger.warning(
            "event=intelligence_query_failed project=%s",
            project_id,
            exc_info=True,
        )
        return APIResponse(
            success=False,
            error="Intelligence query failed. Please try again.",
        )

    return APIResponse(
        success=True,
        data={
            "project_id": project_id,
            "question": body.question,
            "answer": context.formatted
            or "No relevant context found.",
            "entities": [
                {
                    "name": e.name,
                    "type": e.entity_type,
                    "file": e.file_path,
                    "line": e.start_line,
                }
                for e in context.entities
            ],
            "documents": [
                {
                    "section": d.section_name,
                    "content_preview": d.content[:ERROR_TRUNCATION_CHARS],
                }
                for d in context.documents
            ],
            "vector_results": len(context.vector_results),
        },
    )
