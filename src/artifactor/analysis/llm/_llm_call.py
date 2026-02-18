"""Shared LLM call with per-model circuit breaker and rate-limit retry."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import litellm
from circuitbreaker import (  # pyright: ignore[reportUnknownVariableType]
    CircuitBreaker,
    CircuitBreakerError,
)
from litellm.exceptions import RateLimitError as LitellmRateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from artifactor.constants import (
    CB_LLM_FAILURE_THRESHOLD,
    CB_LLM_RECOVERY_TIMEOUT,
    LLM_MAX_OUTPUT_TOKENS,
    RETRY_INITIAL_WAIT,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_WAIT,
)

logger = logging.getLogger(__name__)

# litellm stubs have partially unknown types — typed alias
if TYPE_CHECKING:
    _acompletion: Callable[..., Coroutine[Any, Any, Any]]
else:
    _acompletion = litellm.acompletion


@dataclass(frozen=True)
class LLMCallResult:
    """Structured return from guarded_llm_call with token metadata."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int  # 0 if no cache hit


def _is_non_rate_limit_error(
    thrown_type: type, thrown_value: BaseException
) -> bool:
    """Return True if NOT a rate limit error (should count as CB failure).

    The circuitbreaker library calls this with (thrown_type, thrown_value).
    Rate limit errors are transient backpressure signals, not system failures,
    so we exclude them from circuit breaker failure tracking.
    """
    return not issubclass(thrown_type, LitellmRateLimitError)


# Per-model circuit breaker registry — each model gets independent
# failure tracking so one provider's outage doesn't block fallback
# to another provider.
_breaker_registry: dict[str, CircuitBreaker] = {}  # pyright: ignore[reportUnknownVariableType]


def _get_breaker(model: str) -> CircuitBreaker:  # pyright: ignore[reportUnknownParameterType]
    """Get or create a circuit breaker for the given model."""
    if model not in _breaker_registry:
        _breaker_registry[model] = CircuitBreaker(  # pyright: ignore[reportUnknownMemberType]
            failure_threshold=CB_LLM_FAILURE_THRESHOLD,
            recovery_timeout=CB_LLM_RECOVERY_TIMEOUT,
            expected_exception=_is_non_rate_limit_error,
            name=f"llm_{model}",
        )
    return _breaker_registry[model]


@retry(
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    wait=wait_exponential_jitter(
        initial=RETRY_INITIAL_WAIT, max=RETRY_MAX_WAIT
    ),
    retry=retry_if_exception_type(LitellmRateLimitError),
    reraise=True,
)
async def guarded_llm_call(
    model: str,
    messages: list[dict[str, str]],
    timeout: int,
    *,
    json_mode: bool = True,
) -> LLMCallResult:
    """Per-model circuit-breaker-protected LLM completion with rate-limit retry.

    - Each model has its own circuit breaker (per-model registry).
    - Circuit breaker opens after 5 consecutive non-rate-limit failures,
      recovers after 30s.
    - Tenacity retries rate-limit errors (429) with jittered exponential
      backoff (2s, ~4s, ~8s) to avoid thundering herd.
    - Prompt caching via cache_control_injection_points.
    - Explicit max_tokens=4096 to prevent output truncation.
    """
    breaker = _get_breaker(model)
    if breaker.opened:  # pyright: ignore[reportUnknownMemberType]
        raise CircuitBreakerError(breaker)  # pyright: ignore[reportUnknownArgumentType]
    with breaker:  # pyright: ignore[reportUnknownMemberType]
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "timeout": timeout,
            "max_tokens": LLM_MAX_OUTPUT_TOKENS,
            "cache_control_injection_points": [
                {"location": "message", "role": "system"},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response: Any = await _acompletion(**kwargs)

    usage: Any = response.usage
    cached = getattr(
        getattr(usage, "prompt_tokens_details", None),
        "cached_tokens",
        0,
    )
    input_tokens: int = getattr(usage, "prompt_tokens", 0)
    output_tokens: int = getattr(usage, "completion_tokens", 0)

    if cached and cached > 0:
        logger.info(
            "event=prompt_cache_hit model=%s cached_tokens=%d total_input=%d",
            model,
            cached,
            input_tokens,
        )

    return LLMCallResult(
        content=str(response.choices[0].message.content or ""),
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=int(cached) if cached else 0,
    )
