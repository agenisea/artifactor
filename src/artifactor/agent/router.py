"""Intent-based chat router — keyword classifier for agent dispatch.

Classifies user messages into intents to route to specialized agents
with focused prompts and tool subsets. No LLM call — instant,
deterministic, testable.
"""

from __future__ import annotations

from enum import StrEnum

from artifactor.constants import SEARCH_PRIORITY_WEIGHT


class ChatIntent(StrEnum):
    """Chat query intent categories."""

    LOOKUP = "lookup"
    CODE_EXPLORATION = "code_exploration"
    SEARCH = "search"
    GENERAL = "general"


_INTENT_KEYWORDS: dict[ChatIntent, list[str]] = {
    ChatIntent.LOOKUP: [
        "section",
        "specification",
        "feature",
        "story",
        "stories",
        "endpoint",
        "finding",
        "security",
        "persona",
        "overview",
        "requirement",
        "integration",
        "ui spec",
        "api spec",
    ],
    ChatIntent.CODE_EXPLORATION: [
        "function",
        "class",
        "method",
        "call graph",
        "caller",
        "callee",
        "symbol",
        "data model",
        "entity",
        "schema",
        "module",
        "file",
        "import",
    ],
    ChatIntent.SEARCH: [
        "find",
        "search",
        "locate",
        "where",
        "which files",
        "look for",
        "show me all",
    ],
}


def classify_intent(message: str) -> ChatIntent:
    """Classify a user message into a ChatIntent.

    Scoring rules:
    1. Lowercase the message, count keyword matches per intent.
    2. SEARCH keywords get priority weighting (SEARCH_PRIORITY_WEIGHT)
       to handle "find the features" → SEARCH not LOOKUP.
    3. Highest score wins. Ties → GENERAL. Zero matches → GENERAL.
    4. Multi-word keywords match as substrings.
    """
    lower = message.lower()
    scores: dict[ChatIntent, float] = {}

    for intent, keywords in _INTENT_KEYWORDS.items():
        score = 0.0
        for kw in keywords:
            if kw in lower:
                score += 1.0
        if intent == ChatIntent.SEARCH:
            score *= SEARCH_PRIORITY_WEIGHT
        if score > 0:
            scores[intent] = score

    if not scores:
        return ChatIntent.GENERAL

    max_score = max(scores.values())
    top_intents = [i for i, s in scores.items() if s == max_score]

    if len(top_intents) == 1:
        return top_intents[0]

    return ChatIntent.GENERAL
