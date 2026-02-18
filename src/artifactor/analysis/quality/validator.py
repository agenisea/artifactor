"""Cross-validate static and LLM analysis results."""

from __future__ import annotations

import logging
import re

from artifactor.analysis.llm.schemas import LLMAnalysisResult
from artifactor.analysis.quality.schemas import (
    ValidatedEntity,
    ValidationResult,
)
from artifactor.analysis.quality.scorer import compute_confidence_score
from artifactor.analysis.static.schemas import StaticAnalysisResult

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(
    r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|[a-z]+|\d+"
)


def _tokenize(name: str) -> set[str]:
    """Split a name into lowercase tokens on word boundaries.

    Handles snake_case, camelCase, PascalCase, and dot.separated.
    Tokens shorter than 2 chars are excluded to prevent
    single-letter false matches.
    """
    return {
        t.lower()
        for t in _TOKEN_RE.findall(name)
        if len(t) >= 2
    }


def cross_validate(
    static: StaticAnalysisResult,
    llm: LLMAnalysisResult,
) -> ValidationResult:
    """Reconcile static and LLM analysis results.

    Resolution: AST (deterministic) takes priority over LLM
    (probabilistic) when they disagree. Cross-validated entities
    get higher confidence.
    """
    # Index static entities by (name, file_path)
    static_index: dict[tuple[str, str], ValidatedEntity] = {}
    for entity in static.ast_forest.entities:
        fpath = str(entity.file_path)
        key = (entity.name, fpath)
        ast_score = compute_confidence_score(
            finding=entity.name,
            ast_source=True,
            llm_source=False,
        )
        static_index[key] = ValidatedEntity(
            name=entity.name,
            entity_type=entity.entity_type,
            file_path=fpath,
            line=entity.start_line,
            source="ast",
            confidence=ast_score.value,
            explanation=ast_score.explanation,
        )

    # Index LLM findings by file_path for matching
    llm_file_index: dict[str, list[str]] = {}
    for narrative in llm.narratives:
        concepts: list[str] = []
        for behavior in narrative.behaviors:
            desc = behavior.get("description", "")
            if desc:
                concepts.append(desc)
        if concepts:
            llm_file_index[narrative.file_path] = concepts

    # Cross-validate: look for entities confirmed by LLM
    validated: list[ValidatedEntity] = []
    cross_count = 0
    ast_only = 0

    for _key, entity in static_index.items():
        llm_mentions = llm_file_index.get(entity.file_path, [])
        entity_tokens = _tokenize(entity.name)
        if not entity_tokens:
            # Single-char name or no valid tokens — skip
            found_in_llm = False
        else:
            found_in_llm = any(
                entity_tokens <= _tokenize(mention)
                for mention in llm_mentions
            )
        if found_in_llm:
            xv_score = compute_confidence_score(
                finding=entity.name,
                ast_source=True,
                llm_source=True,
                agreement="high",
            )
            validated.append(
                ValidatedEntity(
                    name=entity.name,
                    entity_type=entity.entity_type,
                    file_path=entity.file_path,
                    line=entity.line,
                    source="cross_validated",
                    confidence=xv_score.value,
                    explanation=xv_score.explanation,
                )
            )
            cross_count += 1
        else:
            validated.append(entity)
            ast_only += 1

    # Add LLM-only findings (rules, risks) as lower-confidence
    llm_only = 0
    for rule in llm.business_rules:
        llm_score = compute_confidence_score(
            finding=rule.rule_text[:80],
            ast_source=False,
            llm_source=True,
        )
        validated.append(
            ValidatedEntity(
                name=rule.rule_text[:80],
                entity_type="business_rule",
                file_path="",
                source="llm",
                confidence=llm_score.value,
                explanation=llm_score.explanation,
            )
        )
        llm_only += 1

    conflicts: list[str] = []
    if cross_count == 0 and len(static_index) > 0 and len(llm.narratives) > 0:
        conflicts.append(
            "No cross-validated entities found despite "
            "both analysis paths producing results"
        )

    return ValidationResult(
        validated_entities=validated,
        conflicts=conflicts,
        ast_only_count=ast_only,
        llm_only_count=llm_only,
        cross_validated_count=cross_count,
    )
