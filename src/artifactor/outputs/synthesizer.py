"""LLM section synthesis with model chain fallback.

Wraps guarded_llm_call() to generate free-form markdown for
section generators. Returns None if all models in the chain fail.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from circuitbreaker import CircuitBreakerError

from artifactor.analysis.llm import LLMCallResult, guarded_llm_call
from artifactor.config import Settings
from artifactor.constants import Confidence

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(
    r"^```(?:markdown|md)?\s*\n(.*?)```\s*$",
    re.DOTALL,
)


@dataclass(frozen=True)
class SynthesisResult:
    """Outcome of LLM section synthesis."""

    content: str  # Markdown
    confidence: float  # Base confidence (0.90 LLM, 0.50 template)
    model_used: str
    input_tokens: int
    output_tokens: int
    context_item_count: int = 0


def _strip_fences(text: str) -> str:
    """Remove wrapping ```markdown fences from LLM output."""
    m = _FENCE_RE.match(text.strip())
    return m.group(1).strip() if m else text.strip()


async def synthesize_section(
    section_name: str,
    system_prompt: str,
    context_data: str,
    settings: Settings,
    context_item_count: int = 0,
) -> SynthesisResult | None:
    """Call LLM to generate section markdown.

    Tries each model in settings.litellm_model_chain.
    Returns None if all models fail (circuit breaker, timeout, etc.).
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context_data},
    ]

    for model_name in settings.litellm_model_chain:
        try:
            result: LLMCallResult = await guarded_llm_call(
                model=model_name,
                messages=messages,
                timeout=settings.llm_timeout_seconds,
                json_mode=False,
            )
            content = _strip_fences(result.content)
            if not content:
                logger.warning(
                    "event=synthesis_empty section=%s model=%s",
                    section_name,
                    model_name,
                )
                continue

            return SynthesisResult(
                content=content,
                confidence=Confidence.LLM_SECTION_RICH,
                model_used=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                context_item_count=context_item_count,
            )
        except CircuitBreakerError:
            logger.warning(
                "event=synthesis_circuit_open section=%s"
                " model=%s",
                section_name,
                model_name,
            )
        except Exception:
            logger.warning(
                "event=synthesis_error section=%s model=%s",
                section_name,
                model_name,
                exc_info=True,
            )

    logger.warning(
        "event=synthesis_all_models_failed section=%s",
        section_name,
    )
    return None
