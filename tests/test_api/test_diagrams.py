"""Tests for diagram API route."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from artifactor.api.dependencies import (
    Repos,
    get_data_service,
    get_project_service,
    get_repos,
)
from artifactor.config import Settings
from artifactor.constants import RelationshipType
from artifactor.logger import AgentLogger
from artifactor.main import app
from artifactor.models.entity import CodeEntityRecord
from artifactor.models.relationship import Relationship
from artifactor.repositories.fakes import (
    FakeConversationRepository,
    FakeDataService,
    FakeDocumentRepository,
    FakeEntityRepository,
    FakeProjectRepository,
    FakeProjectService,
    FakeRelationshipRepository,
)


@pytest.fixture
async def diagram_client(tmp_path: Path):
    """Test client with seeded entities + relationships (no DB)."""
    fake_entity_repo = FakeEntityRepository()
    fake_rel_repo = FakeRelationshipRepository()
    fake_project_repo = FakeProjectRepository()
    fake_repos = Repos(
        project=fake_project_repo,
        document=FakeDocumentRepository(),
        entity=fake_entity_repo,
        relationship=fake_rel_repo,
        conversation=FakeConversationRepository(),
    )
    fake_project_service = FakeProjectService(fake_project_repo)

    # Seed entities
    await fake_entity_repo.bulk_insert(
        [
            CodeEntityRecord(
                project_id="diag-proj",
                name="UserService",
                entity_type="class",
                file_path="src/services/user.py",
                start_line=10,
                end_line=50,
            ),
            CodeEntityRecord(
                project_id="diag-proj",
                name="create_user",
                entity_type="function",
                file_path="src/services/user.py",
                start_line=15,
                end_line=30,
            ),
            CodeEntityRecord(
                project_id="diag-proj",
                name="User",
                entity_type="table",
                file_path="src/models/user.py",
                start_line=1,
                end_line=20,
            ),
        ]
    )

    # Seed relationship
    await fake_rel_repo.bulk_insert(
        [
            Relationship(
                project_id="diag-proj",
                source_file="src/services/user.py",
                source_symbol="create_user",
                target_file="src/models/user.py",
                target_symbol="User",
                relationship_type=RelationshipType.CALLS,
            ),
        ]
    )

    app.state.settings = Settings(
        database_url="sqlite:///:memory:"
    )
    app.state.logger = AgentLogger(
        log_dir=Path(tmp_path / "logs"), level="WARNING"
    )
    app.state.project_service = fake_project_service

    app.dependency_overrides[get_repos] = lambda: fake_repos
    app.dependency_overrides[get_project_service] = (
        lambda: fake_project_service
    )
    app.dependency_overrides[get_data_service] = (
        lambda: FakeDataService()
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


class TestDiagramRoute:
    @pytest.mark.asyncio
    async def test_architecture_diagram_returns_mermaid(
        self, diagram_client: AsyncClient
    ) -> None:
        resp = await diagram_client.get(
            "/api/projects/diag-proj/diagrams/architecture"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["diagram_type"] == "architecture"
        assert data["format"] == "mermaid"
        # Should contain actual Mermaid syntax
        source = data["source"]
        assert "graph TD" in source
        # Should reference our seeded entities
        assert "create_user" in source
        assert "User" in source

    @pytest.mark.asyncio
    async def test_er_diagram_includes_table_entities(
        self, diagram_client: AsyncClient
    ) -> None:
        resp = await diagram_client.get(
            "/api/projects/diag-proj/diagrams/er"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        source = body["data"]["source"]
        assert "erDiagram" in source
        # User is a table entity — should appear in ER
        assert "User" in source

    @pytest.mark.asyncio
    async def test_call_graph_diagram(
        self, diagram_client: AsyncClient
    ) -> None:
        resp = await diagram_client.get(
            "/api/projects/diag-proj/diagrams/call_graph"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        source = body["data"]["source"]
        assert "flowchart LR" in source

    @pytest.mark.asyncio
    async def test_invalid_diagram_type_returns_error(
        self, diagram_client: AsyncClient
    ) -> None:
        resp = await diagram_client.get(
            "/api/projects/diag-proj/diagrams/invalid"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "Unknown diagram type" in body["error"]

    @pytest.mark.asyncio
    async def test_sequence_diagram_returns_mermaid(
        self, diagram_client: AsyncClient
    ) -> None:
        resp = await diagram_client.get(
            "/api/projects/diag-proj/diagrams/sequence"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        source = body["data"]["source"]
        assert "sequenceDiagram" in source
        assert "not yet supported" not in source
        # Seeded fixture has create_user -> User call
        assert "create_user" in source

    @pytest.mark.asyncio
    async def test_empty_project_returns_minimal_diagram(
        self, diagram_client: AsyncClient
    ) -> None:
        resp = await diagram_client.get(
            "/api/projects/nonexistent/diagrams/architecture"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "graph TD" in body["data"]["source"]
