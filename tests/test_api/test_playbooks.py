"""Tests for playbook gallery API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai.models.test import TestModel

from artifactor.main import app
from tests.conftest import setup_test_app


@pytest.fixture
async def client(tmp_path: Path):
    """Test client with fake repos (no database)."""
    setup_test_app(
        tmp_path,
        agent_model=TestModel(
            custom_output_args={
                "message": "Test response.",
                "citations": [],
                "confidence": None,
                "tools_used": [],
            }
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


class TestPlaybookListEndpoint:
    @pytest.mark.asyncio
    async def test_returns_five_playbooks(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/playbooks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 5

    @pytest.mark.asyncio
    async def test_each_entry_has_required_fields(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/playbooks")
        for entry in resp.json()["data"]:
            assert "name" in entry
            assert "title" in entry
            assert "mcp_prompt" in entry
            assert "step_count" in entry
            assert "tools_used" in entry
            assert isinstance(entry["tags"], list)

    @pytest.mark.asyncio
    async def test_names_are_correct(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/playbooks")
        names = {e["name"] for e in resp.json()["data"]}
        assert names == {
            "fix-bug",
            "write-tests",
            "review-code",
            "explain-repo",
            "migration-plan",
        }


class TestPlaybookDetailEndpoint:
    @pytest.mark.asyncio
    async def test_returns_full_playbook(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/playbooks/fix-bug")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["name"] == "fix-bug"
        assert data["mcp_prompt"] == "fix_bug"
        assert isinstance(data["steps"], list)
        assert len(data["steps"]) >= 3
        assert "example_prompt" in data
        assert len(data["example_prompt"]) > 10

    @pytest.mark.asyncio
    async def test_steps_have_description_and_tool(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/playbooks/fix-bug")
        for step in resp.json()["data"]["steps"]:
            assert "description" in step
            assert "tool" in step

    @pytest.mark.asyncio
    async def test_nonexistent_playbook(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/playbooks/nonexistent"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "not found" in body["error"].lower()
