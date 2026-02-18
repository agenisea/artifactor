"""Frozen dataclasses for playbook metadata."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlaybookStep:
    """One descriptive step in a playbook workflow."""

    description: str
    tool: str


@dataclass(frozen=True)
class PlaybookMeta:
    """Summary metadata for gallery listing (no steps)."""

    name: str
    title: str
    description: str
    agent: str
    difficulty: str
    estimated_time: str
    mcp_prompt: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    step_count: int = 0
    tools_used: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Playbook:
    """Full playbook with steps and example prompt."""

    name: str
    title: str
    description: str
    agent: str
    difficulty: str
    estimated_time: str
    mcp_prompt: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    steps: tuple[PlaybookStep, ...] = field(default_factory=tuple)
    example_prompt: str = ""

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def tools_used(self) -> tuple[str, ...]:
        seen: list[str] = []
        for step in self.steps:
            if step.tool not in seen:
                seen.append(step.tool)
        return tuple(seen)

    def to_meta(self) -> PlaybookMeta:
        return PlaybookMeta(
            name=self.name,
            title=self.title,
            description=self.description,
            agent=self.agent,
            difficulty=self.difficulty,
            estimated_time=self.estimated_time,
            mcp_prompt=self.mcp_prompt,
            tags=self.tags,
            step_count=self.step_count,
            tools_used=self.tools_used,
        )
