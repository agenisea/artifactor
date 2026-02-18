"""Combined LLM analysis: narrative + rules + risks in a single call."""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from circuitbreaker import CircuitBreakerError

from artifactor.analysis.llm._llm_call import guarded_llm_call
from artifactor.analysis.llm.schemas import (
    BusinessRule,
    ModuleNarrative,
    RiskIndicator,
)
from artifactor.config import Settings
from artifactor.constants import ConfidenceLevel
from artifactor.ingestion.schemas import CodeChunk
from artifactor.prompts import (
    COMBINED_ANALYSIS_PROMPT,
    build_analysis_prompt,
)

logger = logging.getLogger(__name__)

# Type alias for the combined result
CombinedResult = tuple[
    ModuleNarrative, list[BusinessRule], list[RiskIndicator]
]


async def analyze_chunk(
    chunk: CodeChunk,
    language: str,
    settings: Settings | None = None,
) -> CombinedResult:
    """Analyze a code chunk with a single LLM call.

    Returns (narrative, rules, risks) from one combined prompt.
    Uses primary→fallback model pattern. Returns empty defaults
    on any failure.
    """
    if settings is None:
        settings = Settings()

    file_path = str(chunk.file_path)
    user_prompt = build_analysis_prompt(
        chunk.content, file_path, language
    )

    messages = [
        {"role": "system", "content": COMBINED_ANALYSIS_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    for model in settings.litellm_model_chain:
        try:
            result = await guarded_llm_call(
                model, messages, settings.llm_timeout_seconds
            )
            return _parse_combined(result.content, file_path)
        except CircuitBreakerError:
            logger.warning(
                "event=circuit_open model=%s component=combined file=%s",
                model,
                file_path,
            )
            continue
        except Exception:
            logger.warning(
                "event=combined_failed model=%s file=%s",
                model,
                file_path,
                exc_info=True,
            )
            continue

    # All models failed or circuit open
    return (
        ModuleNarrative(
            file_path=file_path,
            purpose="Analysis unavailable",
            confidence=ConfidenceLevel.LOW,
        ),
        [],
        [],
    )


def _parse_combined(
    raw_json: str, file_path: str
) -> CombinedResult:
    """Parse combined LLM JSON into (narrative, rules, risks)."""
    try:
        data = cast(dict[str, Any], json.loads(raw_json))
    except json.JSONDecodeError:
        logger.warning(
            "event=combined_parse_failed file=%s response_len=%d",
            file_path,
            len(raw_json),
        )
        return (
            ModuleNarrative(
                file_path=file_path,
                purpose="Failed to parse response",
                confidence=ConfidenceLevel.LOW,
            ),
            [],
            [],
        )

    narrative = _extract_narrative(data, file_path)
    rules = _extract_rules(data)
    risks = _extract_risks(data)
    return (narrative, rules, risks)


def _extract_narrative(
    data: dict[str, Any], file_path: str
) -> ModuleNarrative:
    """Extract narrative fields from combined response."""
    return ModuleNarrative(
        file_path=file_path,
        purpose=str(data.get("purpose", "")),
        confidence=str(data.get("confidence", ConfidenceLevel.MEDIUM)),
        behaviors=_normalize_entries(data.get("behaviors", [])),
        domain_concepts=_normalize_entries(
            data.get("domain_concepts", [])
        ),
        citations=_collect_citations(data),
    )


def _extract_rules(data: dict[str, Any]) -> list[BusinessRule]:
    """Extract business rules from combined response."""
    rules_data = data.get("rules", [])
    if not isinstance(rules_data, list):
        return []

    typed_items = cast(list[Any], rules_data)
    rules: list[BusinessRule] = []
    for raw_item in typed_items:
        if not isinstance(raw_item, dict):
            continue
        item = cast(dict[str, Any], raw_item)
        try:
            rules.append(
                BusinessRule(
                    rule_text=str(item.get("rule_text", "")),
                    rule_type=str(
                        item.get("rule_type", "validation")
                    ),
                    condition=str(item.get("condition", "")),
                    consequence=str(
                        item.get("consequence", "")
                    ),
                    confidence=str(
                        item.get("confidence", ConfidenceLevel.MEDIUM)
                    ),
                    affected_entities=cast(
                        list[str],
                        item.get("affected_entities", []),
                    ),
                    citations=cast(
                        list[str],
                        item.get("citations", []),
                    ),
                )
            )
        except Exception:
            continue

    return rules


def _extract_risks(data: dict[str, Any]) -> list[RiskIndicator]:
    """Extract risk indicators from combined response."""
    risks_data = data.get("risks", [])
    if not isinstance(risks_data, list):
        return []

    typed_items = cast(list[Any], risks_data)
    risks: list[RiskIndicator] = []
    for raw_item in typed_items:
        if not isinstance(raw_item, dict):
            continue
        item = cast(dict[str, Any], raw_item)
        try:
            risks.append(
                RiskIndicator(
                    risk_type=str(
                        item.get("risk_type", "complexity")
                    ),
                    severity=str(
                        item.get("severity", ConfidenceLevel.MEDIUM)
                    ),
                    title=str(item.get("title", "")),
                    description=str(
                        item.get("description", "")
                    ),
                    file_path=str(item.get("file_path", "")),
                    line=int(item.get("line", 0)),
                    recommendations=cast(
                        list[str],
                        item.get("recommendations", []),
                    ),
                    confidence=str(
                        item.get("confidence", ConfidenceLevel.MEDIUM)
                    ),
                )
            )
        except Exception:
            continue

    return risks


def _normalize_entries(raw: Any) -> list[dict[str, str]]:
    """Normalize LLM dict entries — coerce lists to strings, skip None."""
    if not isinstance(raw, list):
        return []
    items = cast(list[Any], raw)
    result: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entry = cast(dict[str, Any], item)
        normalized: dict[str, str] = {}
        for k, v in entry.items():
            if v is None:
                continue
            if isinstance(v, list):
                normalized[str(k)] = ", ".join(
                    str(x) for x in cast(list[Any], v)
                )
            else:
                normalized[str(k)] = str(v)
        result.append(normalized)
    return result


def _collect_citations(data: dict[str, Any]) -> list[str]:
    """Collect all citation strings from the combined response."""
    citations: list[str] = []
    sections = ("behaviors", "domain_concepts", "rules", "risks")
    for section in sections:
        items: Any = data.get(section, [])
        if not isinstance(items, list):
            continue
        for raw_entry in cast(list[Any], items):
            if not isinstance(raw_entry, dict):
                continue
            entry = cast(dict[str, Any], raw_entry)
            raw_cites: Any = entry.get("citations", [])
            if isinstance(raw_cites, list):
                citations.extend(
                    str(c) for c in cast(list[Any], raw_cites)
                )
    return citations
