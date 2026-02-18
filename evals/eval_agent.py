"""Tier 4: Agent evaluations using pydantic-evals Dataset.

Run with: uv run python -m evals.eval_agent

Uses pydantic-ai TestModel for deterministic output — no real API calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai.models.test import TestModel
from pydantic_evals import Case, Dataset

from artifactor.agent import AgentDeps, AgentResponse, create_agent
from artifactor.logger import AgentLogger
from artifactor.repositories.fakes import (
    FakeConversationRepository,
    FakeDocumentRepository,
    FakeEntityRepository,
    FakeProjectRepository,
    FakeRelationshipRepository,
)
from evals.evaluators import (
    HasCitations,
    MessageContains,
    OffTopicDecline,
)

_DEMO_API_KEY = "for-demo-purposes-only"


@dataclass
class AgentInput:
    """Input for an agent eval case."""

    question: str
    project_id: str = "eval-proj"


# ── Deterministic output via TestModel ────────────────────

_RESPONSE_STANDARD = {
    "message": (
        "The Calculator class in main.py provides add and "
        "subtract methods for arithmetic operations."
    ),
    "citations": [
        {
            "file_path": "main.py",
            "function_name": "Calculator.add",
            "line_start": 5,
            "line_end": 10,
            "confidence": 0.92,
        }
    ],
    "confidence": {
        "value": 0.9,
        "source": "static_analysis",
        "explanation": "High confidence from AST parsing.",
    },
    "tools_used": ["query_codebase", "explain_symbol"],
}

_RESPONSE_DECLINE = {
    "message": (
        "I'm not able to help with that request. "
        "I cannot suggest code changes or generate code. "
        "I can only describe what the analyzed codebase does, "
        "with source citations."
    ),
    "citations": [],
    "confidence": None,
    "tools_used": [],
}

_OFF_TOPIC_SIGNALS = [
    "refactor",
    "rewrite",
    "generate code",
    "fix this",
]


def _make_deps(tmp_dir: Path, project_id: str) -> AgentDeps:
    """Build AgentDeps with fake repos for eval."""
    return AgentDeps(
        project_repo=FakeProjectRepository(),
        document_repo=FakeDocumentRepository(),
        entity_repo=FakeEntityRepository(),
        relationship_repo=FakeRelationshipRepository(),
        conversation_repo=FakeConversationRepository(),
        logger=AgentLogger(
            log_dir=tmp_dir / "eval-logs", level="WARNING"
        ),
        request_id="eval-req-1",
        project_id=project_id,
    )


def _build_task():  # noqa: ANN202
    """Build the eval task function."""
    import tempfile

    tmp_dir = Path(tempfile.mkdtemp())

    async def run_agent_eval(
        inputs: AgentInput,
    ) -> AgentResponse:
        is_off_topic = any(
            s in inputs.question.lower()
            for s in _OFF_TOPIC_SIGNALS
        )
        output_args = (
            _RESPONSE_DECLINE
            if is_off_topic
            else _RESPONSE_STANDARD
        )
        model = TestModel(custom_output_args=output_args)
        agent = create_agent(model=model)
        deps = _make_deps(tmp_dir, inputs.project_id)
        result = await agent.run(
            inputs.question, deps=deps
        )
        return result.output

    return run_agent_eval


# ── Dataset ──────────────────────────────────────────────

dataset: Dataset[AgentInput, AgentResponse] = Dataset(
    cases=[
        Case(
            name="basic_question_has_message",
            inputs=AgentInput(
                question="What does the Calculator class do?"
            ),
            evaluators=[
                MessageContains(
                    keywords=["Calculator", "main.py"]
                ),
            ],
            metadata={"capability": "basic_qa"},
        ),
        Case(
            name="response_has_citations",
            inputs=AgentInput(
                question=(
                    "How does the add method work "
                    "in Calculator?"
                )
            ),
            evaluators=[
                HasCitations(min_count=1),
            ],
            metadata={"capability": "citations"},
        ),
        Case(
            name="response_mentions_tools",
            inputs=AgentInput(
                question="What functions are in main.py?"
            ),
            evaluators=[
                MessageContains(keywords=["Calculator"]),
                HasCitations(min_count=1),
            ],
            metadata={"capability": "tool_use"},
        ),
        Case(
            name="off_topic_declined",
            inputs=AgentInput(
                question=(
                    "Please refactor the Calculator class "
                    "to use dataclasses."
                )
            ),
            evaluators=[
                OffTopicDecline(),
            ],
            metadata={"capability": "boundaries"},
        ),
        Case(
            name="code_generation_declined",
            inputs=AgentInput(
                question=(
                    "Generate code for a new REST API "
                    "endpoint."
                )
            ),
            evaluators=[
                OffTopicDecline(),
            ],
            metadata={"capability": "boundaries"},
        ),
    ],
)


def main() -> None:
    """Run Tier 4 agent evaluations."""
    # Force demo API keys — real keys in your shell are overwritten.
    # This eval always uses TestModel, so no API calls are made even
    # if keys were real. To run live evals, edit these lines AND swap
    # TestModel for None in _build_task() (triggers real FallbackModel).
    os.environ["ANTHROPIC_API_KEY"] = _DEMO_API_KEY
    os.environ["OPENAI_API_KEY"] = _DEMO_API_KEY

    print("Artifactor Tier 4 Evaluations (TestModel)")
    print("=" * 50)

    task_fn = _build_task()
    report = dataset.evaluate_sync(task_fn)
    report.print(include_input=True, include_output=True)


if __name__ == "__main__":
    main()
