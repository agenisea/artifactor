"""Tests for resolve_model() shared helper."""

from __future__ import annotations

from unittest.mock import patch

from pydantic_ai.models.test import TestModel

from artifactor.agent import resolve_model
from artifactor.agent.agent import (
    resolve_model as resolve_model_direct,
)


class TestResolveModel:
    def test_passthrough_when_model_provided(self) -> None:
        """Non-None model is returned unchanged."""
        model = TestModel()
        assert resolve_model(model) is model

    def test_reads_settings_when_none(self) -> None:
        """None model reads Settings and returns a model."""
        with patch(
            "artifactor.config.Settings"
        ) as mock_settings_cls:
            mock_settings = mock_settings_cls.return_value
            mock_settings.pydantic_ai_models = [
                "openai/gpt-4.1-mini"
            ]
            result = resolve_model(None)
        assert result == "openai/gpt-4.1-mini"

    def test_fallback_model_for_multi_chain(self) -> None:
        """Multi-model chain wraps in FallbackModel."""
        with patch(
            "artifactor.config.Settings"
        ) as mock_settings_cls:
            mock_settings = mock_settings_cls.return_value
            mock_settings.pydantic_ai_models = [
                "openai:gpt-4.1-mini",
                "openai:gpt-4.0-mini",
            ]
            result = resolve_model(None)
        from pydantic_ai.models.fallback import (
            FallbackModel,
        )

        assert isinstance(result, FallbackModel)

    def test_importable_from_agent_package(self) -> None:
        """resolve_model is re-exported from artifactor.agent."""
        assert resolve_model is resolve_model_direct
