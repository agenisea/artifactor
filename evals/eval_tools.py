"""Tier 3: Deterministic tool evaluations using pydantic-evals Dataset.

Run with: uv run python -m evals.eval_tools
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_evals import Case, Dataset

from evals.evaluators import (
    ContainsEntities,
    OutputMatchesExpected,
    SectionComplete,
)


@dataclass
class ToolInput:
    """Simulated tool invocation input."""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)


# ── Simulated tool outputs for deterministic testing ──────

SIMULATED_OUTPUTS: dict[str, str] = {
    "query_codebase_auth": (
        "The Calculator class has add and subtract methods. "
        "Authentication uses JWT tokens in auth/handler.py:15."
    ),
    "get_specification_features": (
        "# Features\n"
        "## Authentication\nJWT-based login flow.\n"
        "## Data Models\nUser and Product entities.\n"
    ),
    "search_entities_calculator": (
        "Found 3 entities:\n"
        "  Calculator (class) at src/calc.py:1\n"
        "  add (function) at src/calc.py:5\n"
        "  subtract (function) at src/calc.py:10"
    ),
    "explain_symbol_greet": (
        "Entities at src/greet.py:\n"
        "  - greet (function) lines 1-5\n"
        "Callers:\n"
        "  - src/main.py:main"
    ),
    "get_api_endpoints_all": (
        "Discovered API endpoints:\n"
        "  GET /api/health [src/api/health.py:10]\n"
        "  POST /api/projects [src/api/projects.py:20]"
    ),
}


async def run_tool(inputs: ToolInput) -> str:
    """Simulate tool execution for deterministic evaluation."""
    key = f"{inputs.tool}_{next(iter(inputs.args.values()), 'all')}"
    return SIMULATED_OUTPUTS.get(
        key,
        f"No simulated output for {inputs.tool}",
    )


# ── Dataset ──────────────────────────────────────────────

dataset: Dataset[ToolInput, str] = Dataset(
    cases=[
        Case(
            name="query_codebase_finds_entities",
            inputs=ToolInput(
                tool="query_codebase",
                args={"question": "auth"},
            ),
            evaluators=[
                ContainsEntities(
                    entities=["Calculator", "JWT", "auth"]
                ),
            ],
            metadata={"capability": "search"},
        ),
        Case(
            name="get_specification_has_sections",
            inputs=ToolInput(
                tool="get_specification",
                args={"section": "features"},
            ),
            evaluators=[
                SectionComplete(
                    required=["Authentication", "Data Models"]
                ),
            ],
            metadata={"capability": "specification"},
        ),
        Case(
            name="search_entities_finds_calculator",
            inputs=ToolInput(
                tool="search_entities",
                args={"query": "calculator"},
            ),
            evaluators=[
                ContainsEntities(
                    entities=["Calculator", "add", "subtract"]
                ),
            ],
            metadata={"capability": "entity_search"},
        ),
        Case(
            name="explain_symbol_has_callers",
            inputs=ToolInput(
                tool="explain_symbol",
                args={"symbol": "greet"},
            ),
            expected_output="greet",
            evaluators=[
                OutputMatchesExpected(),
                ContainsEntities(entities=["greet", "main"]),
            ],
            metadata={"capability": "symbol_explain"},
        ),
        Case(
            name="get_api_endpoints_lists_routes",
            inputs=ToolInput(
                tool="get_api_endpoints",
                args={"filter": "all"},
            ),
            evaluators=[
                ContainsEntities(
                    entities=["/api/health", "/api/projects"]
                ),
            ],
            metadata={"capability": "api_discovery"},
        ),
    ],
)


def main() -> None:
    """Run all Tier 3 evaluations."""
    print("Artifactor Tier 3 Evaluations (pydantic-evals)")
    print("=" * 50)
    report = dataset.evaluate_sync(run_tool)
    report.print(include_input=True, include_output=True)


if __name__ == "__main__":
    main()
