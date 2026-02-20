"""Tests for log_request intent parameter."""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from pathlib import Path

import pytest

from artifactor.logger import AgentLogger


class TestLogRequestIntent:
    @pytest.fixture
    def agent_logger(
        self, tmp_path: Path
    ) -> Generator[AgentLogger, None, None]:
        log = logging.getLogger("artifactor.agent")
        log.handlers.clear()
        yield AgentLogger(log_dir=tmp_path / "logs")
        log.handlers.clear()

    def test_intent_in_log_record(
        self, agent_logger: AgentLogger, tmp_path: Path
    ) -> None:
        agent_logger.log_request(
            request_id="req-1",
            query="show features",
            model="test-model",
            tokens=100,
            tools_called=["list_features"],
            duration_ms=50.0,
            intent="lookup",
        )
        log_file = tmp_path / "logs" / "agent.log"
        content = log_file.read_text()
        record = json.loads(content.strip())
        assert record["intent"] == "lookup"

    def test_intent_default_empty(
        self, agent_logger: AgentLogger, tmp_path: Path
    ) -> None:
        agent_logger.log_request(
            request_id="req-2",
            query="hello",
            model="test-model",
            tokens=10,
            tools_called=[],
            duration_ms=5.0,
        )
        log_file = tmp_path / "logs" / "agent.log"
        content = log_file.read_text()
        record = json.loads(content.strip())
        assert record["intent"] == ""
