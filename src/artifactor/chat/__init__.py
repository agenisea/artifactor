"""Chat module: RAG pipeline, conversation management, citations."""

from artifactor.chat.citations import (
    filter_valid_citations,
    format_citation,
    format_citations_block,
    verify_citations,
)
from artifactor.chat.conversation import (
    add_assistant_message,
    add_user_message,
    create_conversation,
    get_conversation,
    get_history,
    parse_citations_json,
)
from artifactor.chat.rag_pipeline import (
    RetrievedContext,
    VectorResult,
    retrieve_context,
)

__all__ = [
    "RetrievedContext",
    "VectorResult",
    "add_assistant_message",
    "add_user_message",
    "create_conversation",
    "filter_valid_citations",
    "format_citation",
    "format_citations_block",
    "get_conversation",
    "get_history",
    "parse_citations_json",
    "retrieve_context",
    "verify_citations",
]
