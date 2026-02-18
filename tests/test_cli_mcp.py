"""Tests for the MCP CLI subcommand."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from artifactor.cli import _build_parser


class TestMcpArgParsing:
    def test_mcp_subcommand_registered(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["mcp"])
        assert args.command == "mcp"

    def test_mcp_project_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            ["mcp", "--project", "abc-123"]
        )
        assert args.project == "abc-123"

    def test_mcp_project_short_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            ["mcp", "-p", "abc-123"]
        )
        assert args.project == "abc-123"

    def test_mcp_db_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            ["mcp", "--db", "/tmp/test.db"]
        )
        assert args.db == "/tmp/test.db"

    def test_mcp_defaults(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["mcp"])
        assert args.project is None
        assert args.db is None
        assert args.transport == "stdio"
        assert args.host == "0.0.0.0"
        assert args.port == 8001

    def test_mcp_combined_flags(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            ["mcp", "-p", "proj-1", "--db", "/data/a.db"]
        )
        assert args.project == "proj-1"
        assert args.db == "/data/a.db"

    def test_mcp_transport_sse(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            ["mcp", "--transport", "sse"]
        )
        assert args.transport == "sse"

    def test_mcp_transport_short_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["mcp", "-t", "sse"])
        assert args.transport == "sse"

    def test_mcp_host_and_port(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            [
                "mcp",
                "--host",
                "127.0.0.1",
                "--port",
                "9000",
            ]
        )
        assert args.host == "127.0.0.1"
        assert args.port == 9000

    def test_mcp_all_transport_flags(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            [
                "mcp",
                "-t",
                "sse",
                "--host",
                "10.0.0.1",
                "--port",
                "3333",
                "-p",
                "proj-1",
            ]
        )
        assert args.transport == "sse"
        assert args.host == "10.0.0.1"
        assert args.port == 3333
        assert args.project == "proj-1"


class TestMcpRunner:
    def test_run_mcp_invalid_db_exits(self) -> None:
        """--db pointing to nonexistent file exits with error."""
        from artifactor.cli import _run_mcp

        args = MagicMock()
        args.db = "/nonexistent/path/to/db.sqlite"
        args.project = None

        with pytest.raises(SystemExit) as exc_info:
            _run_mcp(args)
        assert exc_info.value.code == 1

    def test_run_mcp_none_db_skips_validation(
        self,
    ) -> None:
        """--db=None doesn't trigger path validation."""
        from artifactor.cli import _run_mcp

        args = MagicMock()
        args.db = None
        args.project = None

        with patch(
            "asyncio.run"
        ) as mock_asyncio_run:
            _run_mcp(args)
            mock_asyncio_run.assert_called_once()

    @pytest.mark.filterwarnings(
        "ignore:coroutine.*was never awaited:RuntimeWarning"
    )
    @pytest.mark.asyncio
    async def test_setup_and_run_mcp_configures(
        self,
    ) -> None:
        """Verify configure() is called and mcp.run_async invoked."""
        from artifactor.cli import _setup_and_run_mcp

        mock_mcp = MagicMock()
        mock_mcp.run_async = AsyncMock()

        with patch(
            "artifactor.mcp.server.mcp", mock_mcp
        ), patch(
            "artifactor.mcp.mcp", mock_mcp
        ):
            await _setup_and_run_mcp(
                "sqlite+aiosqlite:///:memory:",
                "test-project",
                transport="stdio",
            )

            mock_mcp.run_async.assert_called_once_with(
                transport="stdio"
            )

    @pytest.mark.asyncio
    async def test_setup_and_run_mcp_sets_default_project(
        self,
    ) -> None:
        """Verify default project ID is set via configure()."""
        from artifactor.cli import _setup_and_run_mcp
        from artifactor.mcp.server import (
            get_default_project_id,
        )

        mock_mcp = MagicMock()
        mock_mcp.run_async = AsyncMock()

        with patch(
            "artifactor.mcp.server.mcp", mock_mcp
        ), patch(
            "artifactor.mcp.mcp", mock_mcp
        ):
            await _setup_and_run_mcp(
                "sqlite+aiosqlite:///:memory:",
                "my-proj-id",
                transport="stdio",
            )

            assert (
                get_default_project_id() == "my-proj-id"
            )

    @pytest.mark.asyncio
    async def test_setup_and_run_mcp_disposes_on_error(
        self,
    ) -> None:
        """Verify engine.dispose() is called even on failure."""
        from artifactor.cli import _setup_and_run_mcp

        mock_mcp = MagicMock()
        mock_mcp.run_async = AsyncMock(
            side_effect=RuntimeError("transport error")
        )

        with (
            patch(
                "artifactor.mcp.server.mcp", mock_mcp
            ),
            patch(
                "artifactor.mcp.mcp", mock_mcp
            ),
            pytest.raises(
                RuntimeError, match="transport error"
            ),
        ):
            await _setup_and_run_mcp(
                "sqlite+aiosqlite:///:memory:",
                None,
                transport="stdio",
            )

    @pytest.mark.asyncio
    async def test_setup_and_run_mcp_sse_transport(
        self,
    ) -> None:
        """Verify SSE transport passes host/port to run_async."""
        from artifactor.cli import _setup_and_run_mcp

        mock_mcp = MagicMock()
        mock_mcp.run_async = AsyncMock()

        with patch(
            "artifactor.mcp.server.mcp", mock_mcp
        ), patch(
            "artifactor.mcp.mcp", mock_mcp
        ):
            await _setup_and_run_mcp(
                "sqlite+aiosqlite:///:memory:",
                None,
                transport="sse",
                host="0.0.0.0",
                port=8001,
            )

            mock_mcp.run_async.assert_called_once_with(
                transport="sse",
                host="0.0.0.0",
                port=8001,
            )
