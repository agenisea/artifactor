"""Tests for API routes using httpx AsyncClient."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai.models.test import TestModel

from artifactor.api.dependencies import (
    Repos,
    get_project_service,
    get_repos,
)
from artifactor.constants import ProjectStatus
from artifactor.main import app
from artifactor.models.entity import CodeEntityRecord
from tests.conftest import setup_test_app


@pytest.fixture
async def client(tmp_path: Path):
    """Create a test client with fake repos (no database)."""
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

    app.dependency_overrides.clear()


class TestHealthRoutes:
    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_detailed(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert "components" in data


class TestProjectRoutes:
    @pytest.mark.asyncio
    async def test_list_projects_empty(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/projects")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == []

    @pytest.mark.asyncio
    async def test_create_and_get_project(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects",
            json={"name": "test-project", "branch": "main"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        project_id = body["data"]["id"]
        assert body["data"]["name"] == "test-project"

        # GET by id
        resp = await client.get(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "test-project"

    @pytest.mark.asyncio
    async def test_get_nonexistent_project(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/projects/nonexistent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "not found" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_delete_project(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects",
            json={"name": "to-delete"},
        )
        project_id = resp.json()["data"]["id"]

        resp = await client.delete(
            f"/api/projects/{project_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify deleted
        resp = await client.get(f"/api/projects/{project_id}")
        assert resp.json()["success"] is False

    @pytest.mark.asyncio
    async def test_analyze_project(
        self, client: AsyncClient
    ) -> None:
        from unittest.mock import AsyncMock, patch

        from artifactor.services.analysis_service import (
            AnalysisResult,
        )

        resp = await client.post(
            "/api/projects",
            json={"name": "to-analyze"},
        )
        project_id = resp.json()["data"]["id"]

        mock_result = AnalysisResult(
            project_id=project_id, total_duration_ms=1.0
        )
        with patch(
            "artifactor.api.routes.projects.run_analysis",
            new=AsyncMock(return_value=mock_result),
        ):
            resp = await client.post(
                f"/api/projects/{project_id}/analyze"
            )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get(
            "content-type", ""
        )

    @pytest.mark.asyncio
    async def test_project_status(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects",
            json={"name": "status-check"},
        )
        project_id = resp.json()["data"]["id"]

        resp = await client.get(
            f"/api/projects/{project_id}/status"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == ProjectStatus.PENDING


class TestPauseRoute:
    @pytest.mark.asyncio
    async def test_pause_pending_project_returns_error(
        self, client: AsyncClient
    ) -> None:
        """Pause on a non-analyzing project fails."""
        resp = await client.post(
            "/api/projects",
            json={"name": "pending-proj"},
        )
        project_id = resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/projects/{project_id}/pause"
        )
        body = resp.json()
        assert body["success"] is False
        assert "Cannot pause" in body["error"]

    @pytest.mark.asyncio
    async def test_pause_nonexistent_project_returns_error(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/nonexistent-id/pause"
        )
        body = resp.json()
        assert body["success"] is False
        assert "not found" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_pause_analyzed_project_returns_error(
        self, client: AsyncClient
    ) -> None:
        """Pause on an already-analyzed project fails."""
        resp = await client.post(
            "/api/projects",
            json={"name": "analyzed-proj"},
        )
        project_id = resp.json()["data"]["id"]

        # Manually set status to analyzed
        svc = app.dependency_overrides[
            get_project_service
        ]()
        await svc.try_set_status_immediate(
            project_id,
            {ProjectStatus.PENDING},
            ProjectStatus.ANALYZED,
        )

        resp = await client.post(
            f"/api/projects/{project_id}/pause"
        )
        body = resp.json()
        assert body["success"] is False
        assert "Cannot pause" in body["error"]


class TestSectionRoutes:
    @pytest.mark.asyncio
    async def test_list_sections_empty(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/sections"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == []

    @pytest.mark.asyncio
    async def test_get_section_not_found(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/sections/features"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False

    @pytest.mark.asyncio
    async def test_regenerate_unknown_section(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/fake-id/sections/bogus/regenerate"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "Unknown section" in body["error"]

    @pytest.mark.asyncio
    async def test_regenerate_no_entities(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/fake-id/sections/features/regenerate"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "No entities" in body["error"]

    @pytest.mark.asyncio
    async def test_regenerate_success(
        self, client: AsyncClient
    ) -> None:
        # Seed an entity via the fake repo override
        fake_repos: Repos = app.dependency_overrides[
            get_repos
        ]()
        await fake_repos.entity.bulk_insert(
            [
                CodeEntityRecord(
                    id="test-entity-1",
                    project_id="regen-proj",
                    name="Calculator",
                    entity_type="class",
                    file_path="main.py",
                    start_line=1,
                    end_line=50,
                    language="python",
                )
            ]
        )

        resp = await client.post(
            "/api/projects/regen-proj/sections/"
            "executive_overview/regenerate"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "regenerated"
        assert "confidence" in body["data"]


class TestContentRoutes:
    @pytest.mark.asyncio
    async def test_features_empty(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/features"
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_data_models_empty(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/data-models"
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_api_endpoints_empty(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/api-endpoints"
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_user_stories_empty(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/user-stories"
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_security_empty(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/security"
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_entities_empty(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/entities"
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_entities_by_path(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/entities/main.py"
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestCallGraphRoute:
    @pytest.mark.asyncio
    async def test_call_graph(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/call-graph/main.py/greet"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["symbol"] == "greet"


class TestDiagramRoutes:
    @pytest.mark.asyncio
    async def test_valid_diagram_type(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/diagrams/architecture"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "source" in body["data"]

    @pytest.mark.asyncio
    async def test_invalid_diagram_type(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/diagrams/invalid"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "Unknown diagram type" in body["error"]


class TestConversationRoutes:
    @pytest.mark.asyncio
    async def test_list_conversations_empty(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/conversations"
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/projects/fake-id/conversations/nonexistent"
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False



class TestChatRoute:
    @pytest.mark.asyncio
    async def test_chat_returns_sse(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/fake-id/chat",
            json={"message": "What does this code do?"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get(
            "content-type", ""
        )


class TestIntelligenceRoute:
    @pytest.mark.asyncio
    async def test_query_returns_context(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/fake-id/query",
            json={"question": "What is the main purpose?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert "answer" in data
        assert "entities" in data
        assert "documents" in data
        assert "vector_results" in data
        assert data["question"] == "What is the main purpose?"

    @pytest.mark.asyncio
    async def test_query_empty_project(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/nonexistent/query",
            json={"question": "Anything here?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["entities"] == []
        assert body["data"]["documents"] == []

    @pytest.mark.asyncio
    async def test_query_error_returns_generic_message(
        self, client: AsyncClient
    ) -> None:
        """retrieve_context failure returns success=False, no leak."""
        from unittest.mock import patch

        with patch(
            "artifactor.api.routes.intelligence.retrieve_context",
            side_effect=RuntimeError("secret DB path /data/db"),
        ):
            resp = await client.post(
                "/api/projects/fake-id/query",
                json={"question": "crash me"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "Intelligence query failed" in body["error"]
        assert "/data/db" not in body["error"]


class TestAuthMiddleware:
    @pytest.mark.asyncio
    async def test_no_api_key_config_passes(
        self, client: AsyncClient
    ) -> None:
        """When api_key is empty, all requests pass through."""
        resp = await client.get("/api/projects")
        assert resp.status_code == 200


class TestProjectServiceIntegration:
    @pytest.mark.asyncio
    async def test_project_lifecycle(
        self, client: AsyncClient
    ) -> None:
        """Full lifecycle: create -> list -> status -> delete."""
        # Create
        resp = await client.post(
            "/api/projects",
            json={
                "name": "lifecycle-test",
                "local_path": "/tmp/repo",
            },
        )
        assert resp.json()["success"] is True
        pid = resp.json()["data"]["id"]

        # List
        resp = await client.get("/api/projects")
        names = [p["name"] for p in resp.json()["data"]]
        assert "lifecycle-test" in names

        # Status
        resp = await client.get(f"/api/projects/{pid}/status")
        assert resp.json()["data"]["status"] == ProjectStatus.PENDING

        # Delete
        resp = await client.delete(f"/api/projects/{pid}")
        assert resp.json()["success"] is True

        # Verify gone
        resp = await client.get(f"/api/projects/{pid}")
        assert resp.json()["success"] is False
