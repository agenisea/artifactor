"""Load and validate playbook YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from artifactor.playbooks.schemas import Playbook, PlaybookMeta, PlaybookStep

# The 10 registered MCP tool names.
VALID_TOOLS: frozenset[str] = frozenset(
    {
        "query_codebase",
        "get_specification",
        "list_features",
        "get_data_model",
        "explain_symbol",
        "get_call_graph",
        "get_user_stories",
        "get_api_endpoints",
        "search_code_entities",
        "get_security_findings",
    }
)

# The 5 registered MCP prompt names.
VALID_PROMPTS: frozenset[str] = frozenset(
    {
        "fix_bug",
        "write_tests",
        "review_code",
        "explain_repo",
        "migration_plan",
    }
)

_PLAYBOOKS_DIR = Path(__file__).resolve().parents[3] / "playbooks"


def _playbooks_dir() -> Path:
    """Return the playbooks directory path."""
    return _PLAYBOOKS_DIR


def load_playbook(
    name: str, *, playbooks_dir: Path | None = None
) -> Playbook:
    """Load a single playbook from ``playbooks/{name}.yaml``.

    Raises ``FileNotFoundError`` if the file doesn't exist and
    ``ValueError`` if a step references an unknown tool or the
    ``mcp_prompt`` field is invalid.
    """
    directory = playbooks_dir or _playbooks_dir()

    # Reject path traversal attempts
    if ".." in name or "/" in name or "\\" in name:
        msg = f"Invalid playbook name: {name!r}"
        raise ValueError(msg)

    path = directory / f"{name}.yaml"
    if not path.exists():
        msg = f"Playbook not found: {path}"
        raise FileNotFoundError(msg)

    raw: dict[str, Any] = yaml.safe_load(path.read_text())

    # Validate mcp_prompt
    mcp_prompt = str(raw.get("mcp_prompt", ""))
    if mcp_prompt not in VALID_PROMPTS:
        msg = (
            f"Invalid mcp_prompt '{mcp_prompt}' in playbook "
            f"'{name}'. Must be one of: {sorted(VALID_PROMPTS)}"
        )
        raise ValueError(msg)

    # Parse steps and validate tool names
    steps: list[PlaybookStep] = []
    for i, step_raw in enumerate(raw.get("steps", [])):
        tool = str(step_raw.get("tool", ""))
        if tool not in VALID_TOOLS:
            msg = (
                f"Invalid tool '{tool}' in playbook '{name}' "
                f"step {i}. Must be one of: {sorted(VALID_TOOLS)}"
            )
            raise ValueError(msg)
        steps.append(
            PlaybookStep(
                description=str(step_raw.get("description", "")),
                tool=tool,
            )
        )

    tags_raw = raw.get("tags", [])
    tags = tuple(str(t) for t in tags_raw)

    return Playbook(
        name=str(raw.get("name", name)),
        title=str(raw.get("title", "")),
        description=str(raw.get("description", "")).strip(),
        agent=str(raw.get("agent", "generic")),
        difficulty=str(raw.get("difficulty", "beginner")),
        estimated_time=str(raw.get("estimated_time", "")),
        mcp_prompt=mcp_prompt,
        tags=tags,
        steps=tuple(steps),
        example_prompt=str(raw.get("example_prompt", "")).strip(),
    )


def list_playbooks(
    *, playbooks_dir: Path | None = None
) -> list[PlaybookMeta]:
    """List all playbooks with summary metadata."""
    directory = playbooks_dir or _playbooks_dir()
    if not directory.exists():
        return []

    result: list[PlaybookMeta] = []
    for path in sorted(directory.glob("*.yaml")):
        name = path.stem
        playbook = load_playbook(name, playbooks_dir=directory)
        result.append(playbook.to_meta())
    return result
