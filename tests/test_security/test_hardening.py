"""Tests for security hardening."""

from __future__ import annotations

import hmac
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai.models.test import TestModel

from artifactor.config import Settings
from artifactor.constants import SSEEvent
from artifactor.main import app
from artifactor.playbooks.loader import load_playbook
from tests.conftest import (
    parse_sse_events as _parse_sse_events,
)
from tests.conftest import (
    setup_test_app,
)

# ── Fixtures ──────────────────────────────────────────


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


# ── H3: SSE error sanitization ───────────────────────


class TestSSEErrorSanitization:
    @pytest.mark.asyncio
    async def test_chat_error_is_generic(
        self, client: AsyncClient
    ) -> None:
        """Chat SSE error events must not leak exception details."""
        with patch(
            "artifactor.api.routes.chat.create_agent"
        ) as mock_create:
            mock_agent = MagicMock()
            # agent.iter() returns an async context manager
            # (not a coroutine). Use MagicMock for iter so no
            # unawaited coroutine is created on call.
            mock_iter_cm = AsyncMock()
            mock_iter_cm.__aenter__.side_effect = RuntimeError(
                "secret internal path /app/data/db.sqlite"
            )
            mock_agent.iter.return_value = mock_iter_cm
            mock_create.return_value = mock_agent

            resp = await client.post(
                "/api/projects/test-project/chat",
                json={"message": "Hello"},
            )
            events = _parse_sse_events(resp.text)
            error_events = [
                e for e in events if e["event"] == SSEEvent.ERROR
            ]
            assert len(error_events) >= 1
            data = json.loads(error_events[0]["data"])
            # Must NOT contain the secret path
            assert "secret internal path" not in data["error"]
            assert "/app/data/db.sqlite" not in data["error"]
            # Must contain generic message (not internal details)
            assert (
                "Chat request failed" in data["error"]
            )


# ── M1: Path traversal validation ────────────────────


class TestPathTraversalValidation:
    def test_dotdot_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid playbook"):
            load_playbook("../etc/passwd")

    def test_slash_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid playbook"):
            load_playbook("sub/playbook")

    def test_backslash_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid playbook"):
            load_playbook("sub\\playbook")

    def test_valid_name_still_works(self) -> None:
        """Normal playbook names load fine."""
        pb = load_playbook("fix-bug")
        assert pb.name == "fix-bug"

    @pytest.mark.asyncio
    async def test_api_rejects_traversal(
        self, client: AsyncClient
    ) -> None:
        """Name with '..' is caught by loader validation."""
        resp = await client.get("/api/playbooks/..passwd")
        body = resp.json()
        assert body["success"] is False
        assert "Invalid playbook" in body["error"]


# ── M3: CORS middleware ──────────────────────────────


class TestCORSConfiguration:
    @pytest.mark.asyncio
    async def test_no_cors_headers_by_default(
        self, client: AsyncClient
    ) -> None:
        """When cors_origins is empty, no CORS headers are sent."""
        resp = await client.get("/api/health")
        assert (
            "access-control-allow-origin"
            not in resp.headers
        )

    def test_cors_origins_parsing(self) -> None:
        """Comma-separated string parses into list."""
        settings = Settings(
            database_url="sqlite:///:memory:",
            cors_origins="http://localhost:3000,http://localhost:8080",
        )
        origins = [
            o.strip()
            for o in settings.cors_origins.split(",")
            if o.strip()
        ]
        assert origins == [
            "http://localhost:3000",
            "http://localhost:8080",
        ]

    def test_empty_cors_origins(self) -> None:
        """Empty string produces empty list."""
        settings = Settings(
            database_url="sqlite:///:memory:",
            cors_origins="",
        )
        origins = [
            o.strip()
            for o in settings.cors_origins.split(",")
            if o.strip()
        ]
        assert origins == []


# ── H1: Filesystem browse root restriction ──────────


class TestFilesystemBrowseRoot:
    @pytest.mark.asyncio
    async def test_browse_rejects_outside_root(
        self, client: AsyncClient, tmp_path: Path
    ) -> None:
        """Requests outside browse_root are rejected."""
        root = tmp_path / "allowed"
        root.mkdir()
        app.state.settings = Settings(
            database_url="sqlite:///:memory:",
            browse_root=str(root),
        )
        resp = await client.get(
            "/api/filesystem/browse", params={"path": "/etc"}
        )
        body = resp.json()
        assert body["success"] is False
        assert "Access denied" in body["error"]

    @pytest.mark.asyncio
    async def test_browse_rejects_traversal(
        self, client: AsyncClient, tmp_path: Path
    ) -> None:
        """Path with .. that escapes root is rejected."""
        root = tmp_path / "allowed"
        root.mkdir()
        app.state.settings = Settings(
            database_url="sqlite:///:memory:",
            browse_root=str(root),
        )
        escape = str(root / ".." / "..")
        resp = await client.get(
            "/api/filesystem/browse",
            params={"path": escape},
        )
        body = resp.json()
        assert body["success"] is False
        assert "Access denied" in body["error"]

    @pytest.mark.asyncio
    async def test_browse_within_root_works(
        self, client: AsyncClient, tmp_path: Path
    ) -> None:
        """Requests inside browse_root succeed."""
        root = tmp_path / "allowed"
        sub = root / "subdir"
        sub.mkdir(parents=True)
        app.state.settings = Settings(
            database_url="sqlite:///:memory:",
            browse_root=str(root),
        )
        resp = await client.get(
            "/api/filesystem/browse",
            params={"path": str(root)},
        )
        body = resp.json()
        assert body["success"] is True
        names = [e["name"] for e in body["data"]["entries"]]
        assert "subdir" in names

    @pytest.mark.asyncio
    async def test_browse_parent_clamped_to_root(
        self, client: AsyncClient, tmp_path: Path
    ) -> None:
        """At the root, parent is None."""
        root = tmp_path / "allowed"
        root.mkdir()
        app.state.settings = Settings(
            database_url="sqlite:///:memory:",
            browse_root=str(root),
        )
        resp = await client.get(
            "/api/filesystem/browse",
            params={"path": str(root)},
        )
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["parent"] is None

    @pytest.mark.asyncio
    async def test_browse_error_does_not_leak_path(
        self, client: AsyncClient, tmp_path: Path
    ) -> None:
        """Error messages don't contain resolved paths."""
        root = tmp_path / "allowed"
        root.mkdir()
        app.state.settings = Settings(
            database_url="sqlite:///:memory:",
            browse_root=str(root),
        )
        # A path that exists but is outside root
        resp = await client.get(
            "/api/filesystem/browse",
            params={"path": str(tmp_path)},
        )
        body = resp.json()
        assert body["success"] is False
        assert str(tmp_path) not in body["error"]

    @pytest.mark.asyncio
    async def test_browse_default_root_is_home(
        self, client: AsyncClient
    ) -> None:
        """When browse_root is empty, default is Path.home()."""
        app.state.settings = Settings(
            database_url="sqlite:///:memory:",
            browse_root="",
        )
        resp = await client.get("/api/filesystem/browse")
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["current"] == str(
            Path.home().resolve()
        )


# ── H2: Timing-safe API key comparison ──────────────


class TestTimingSafeAuth:
    def test_auth_uses_timing_safe_comparison(self) -> None:
        """Auth middleware uses hmac.compare_digest."""
        with patch(
            "artifactor.api.middleware.auth.hmac.compare_digest",
            wraps=hmac.compare_digest,
        ) as mock_cmp:
            import asyncio
            from unittest.mock import MagicMock

            from artifactor.api.middleware.auth import (
                ApiKeyMiddleware,
            )

            middleware = ApiKeyMiddleware(app=MagicMock())

            mock_request = MagicMock()
            mock_request.url.path = "/api/projects"
            mock_request.headers.get.return_value = "wrong-key"
            mock_request.app.state.settings = Settings(
                database_url="sqlite:///:memory:",
                api_key="correct-key",
            )

            mock_next = AsyncMock()
            asyncio.get_event_loop().run_until_complete(
                middleware.dispatch(mock_request, mock_next)
            )
            mock_cmp.assert_called_once_with(
                "wrong-key", "correct-key"
            )


# ── Symlink directory traversal protection ────────────


class TestSymlinkTraversal:
    def test_walk_files_skips_dir_symlink_outside_root(
        self, tmp_path: Path
    ) -> None:
        """Directory symlinks that escape the repo root are skipped."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "real.py").write_text("x = 1\n")

        # Create an outside dir with a file
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.py").write_text("SECRET = True\n")

        # Symlink from repo/link -> outside
        (repo / "link").symlink_to(outside)

        import pathspec

        from artifactor.ingestion.language_detector import _walk_files

        empty_spec = pathspec.PathSpec.from_lines("gitignore", [])
        files = _walk_files(repo, set(), empty_spec)
        names = [f.name for f in files]
        assert "real.py" in names
        assert "secret.py" not in names

    def test_walk_source_files_skips_escaped_file_symlink(
        self, tmp_path: Path
    ) -> None:
        """File symlinks pointing outside the repo root are skipped."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "real.py").write_text("x = 1\n")

        # Create a file outside
        outside_file = tmp_path / "secret.txt"
        outside_file.write_text("SECRET\n")

        # Symlink from repo/link.txt -> outside_file
        (repo / "link.txt").symlink_to(outside_file)

        import pathspec

        from artifactor.ingestion.chunker import _walk_source_files

        empty_spec = pathspec.PathSpec.from_lines("gitignore", [])
        files = _walk_source_files(repo, set(), empty_spec)
        names = [f.name for f in files]
        assert "real.py" in names
        assert "link.txt" not in names
