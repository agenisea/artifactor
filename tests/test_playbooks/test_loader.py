"""Tests for playbook loader and schemas."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from artifactor.playbooks.loader import (
    VALID_PROMPTS,
    VALID_TOOLS,
    list_playbooks,
    load_playbook,
)


@pytest.fixture
def playbooks_dir(tmp_path: Path) -> Path:
    """Create a temp directory with test playbook YAML files."""
    d = tmp_path / "playbooks"
    d.mkdir()
    (d / "fix-bug.yaml").write_text(
        dedent("""\
            name: fix-bug
            title: "Fix a Bug"
            description: "Find and fix a bug."
            agent: claude
            difficulty: intermediate
            estimated_time: "2-5 minutes"
            mcp_prompt: fix_bug
            tags:
              - bug-fix
              - debugging
            steps:
              - description: "Search codebase"
                tool: query_codebase
              - description: "Examine symbol"
                tool: explain_symbol
            example_prompt: "Fix the login bug in auth.py."
        """)
    )
    return d


class TestLoadPlaybook:
    def test_loads_valid_playbook(
        self, playbooks_dir: Path
    ) -> None:
        pb = load_playbook(
            "fix-bug", playbooks_dir=playbooks_dir
        )
        assert pb.name == "fix-bug"
        assert pb.title == "Fix a Bug"
        assert pb.mcp_prompt == "fix_bug"
        assert pb.agent == "claude"
        assert pb.difficulty == "intermediate"
        assert pb.step_count == 2
        assert pb.tools_used == (
            "query_codebase",
            "explain_symbol",
        )
        assert "bug-fix" in pb.tags
        assert "Fix the login bug" in pb.example_prompt

    def test_nonexistent_playbook_raises(
        self, playbooks_dir: Path
    ) -> None:
        with pytest.raises(FileNotFoundError):
            load_playbook(
                "nonexistent", playbooks_dir=playbooks_dir
            )

    def test_invalid_tool_raises(
        self, playbooks_dir: Path
    ) -> None:
        (playbooks_dir / "bad-tool.yaml").write_text(
            dedent("""\
                name: bad-tool
                title: "Bad Tool"
                description: "Has invalid tool."
                agent: claude
                difficulty: beginner
                estimated_time: "1 minute"
                mcp_prompt: fix_bug
                tags: []
                steps:
                  - description: "Invalid step"
                    tool: nonexistent_tool
                example_prompt: "Test."
            """)
        )
        with pytest.raises(ValueError, match="nonexistent_tool"):
            load_playbook(
                "bad-tool", playbooks_dir=playbooks_dir
            )

    def test_invalid_mcp_prompt_raises(
        self, playbooks_dir: Path
    ) -> None:
        (playbooks_dir / "bad-prompt.yaml").write_text(
            dedent("""\
                name: bad-prompt
                title: "Bad Prompt"
                description: "Has invalid mcp_prompt."
                agent: claude
                difficulty: beginner
                estimated_time: "1 minute"
                mcp_prompt: fake_prompt
                tags: []
                steps: []
                example_prompt: "Test."
            """)
        )
        with pytest.raises(ValueError, match="fake_prompt"):
            load_playbook(
                "bad-prompt", playbooks_dir=playbooks_dir
            )

    def test_to_meta_conversion(
        self, playbooks_dir: Path
    ) -> None:
        pb = load_playbook(
            "fix-bug", playbooks_dir=playbooks_dir
        )
        meta = pb.to_meta()
        assert meta.name == "fix-bug"
        assert meta.step_count == 2
        assert meta.tools_used == (
            "query_codebase",
            "explain_symbol",
        )
        assert meta.mcp_prompt == "fix_bug"


class TestListPlaybooks:
    def test_lists_all_playbooks(
        self, playbooks_dir: Path
    ) -> None:
        metas = list_playbooks(playbooks_dir=playbooks_dir)
        assert len(metas) == 1
        assert metas[0].name == "fix-bug"

    def test_empty_directory(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        metas = list_playbooks(playbooks_dir=d)
        assert metas == []

    def test_nonexistent_directory(
        self, tmp_path: Path
    ) -> None:
        d = tmp_path / "does-not-exist"
        metas = list_playbooks(playbooks_dir=d)
        assert metas == []


class TestRealPlaybooks:
    """Validate the actual playbook YAML files in playbooks/."""

    def test_all_five_playbooks_load(self) -> None:
        metas = list_playbooks()
        assert len(metas) == 5
        names = {m.name for m in metas}
        assert names == {
            "fix-bug",
            "write-tests",
            "review-code",
            "explain-repo",
            "migration-plan",
        }

    def test_each_playbook_has_valid_mcp_prompt(
        self,
    ) -> None:
        metas = list_playbooks()
        for m in metas:
            assert m.mcp_prompt in VALID_PROMPTS, (
                f"{m.name} has invalid mcp_prompt: "
                f"{m.mcp_prompt}"
            )

    def test_each_playbook_has_valid_tools(self) -> None:
        metas = list_playbooks()
        for m in metas:
            for tool in m.tools_used:
                assert tool in VALID_TOOLS, (
                    f"{m.name} uses invalid tool: {tool}"
                )

    def test_each_playbook_has_steps(self) -> None:
        metas = list_playbooks()
        for m in metas:
            assert m.step_count >= 3, (
                f"{m.name} has only {m.step_count} steps"
            )

    def test_each_playbook_has_example_prompt(
        self,
    ) -> None:
        names = [
            "fix-bug",
            "write-tests",
            "review-code",
            "explain-repo",
            "migration-plan",
        ]
        for name in names:
            pb = load_playbook(name)
            assert len(pb.example_prompt) > 10, (
                f"{name} has no example_prompt"
            )
