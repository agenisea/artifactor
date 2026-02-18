"""Cost aggregator handler -- tracks LLM token costs per trace."""

from __future__ import annotations

from dataclasses import dataclass

from artifactor.observability.events import TraceEvent


@dataclass
class TraceCost:
    """Accumulated cost for a single trace."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    call_count: int = 0


class CostAggregatorHandler:
    """Tracks LLM token costs per trace_id."""

    def __init__(self) -> None:
        self._costs: dict[str, TraceCost] = {}

    @property
    def name(self) -> str:
        return "cost_aggregator"

    async def handle(self, event: TraceEvent) -> None:
        if event.type != "llm_call":
            return
        cost = self._costs.setdefault(
            event.trace_id, TraceCost()
        )
        cost.input_tokens += int(
            event.data.get("input_tokens", 0)
        )
        cost.output_tokens += int(
            event.data.get("output_tokens", 0)
        )
        cost.total_cost += float(event.data.get("cost", 0.0))
        cost.call_count += 1

    def get_cost(self, trace_id: str) -> TraceCost:
        return self._costs.get(trace_id, TraceCost())

    def all_costs(self) -> dict[str, TraceCost]:
        return dict(self._costs)
