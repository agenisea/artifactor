"""Tests for Settings model chain validators."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from artifactor.config import Settings


class TestModelChainParsing:
    def test_comma_separated_string_parsed_to_list(self) -> None:
        """_parse_chain splits comma-separated strings."""
        s = Settings(litellm_model_chain="model-a,model-b")  # type: ignore[arg-type]
        assert s.litellm_model_chain == ["model-a", "model-b"]

    def test_comma_separated_with_spaces(self) -> None:
        s = Settings(litellm_model_chain="model-a , model-b")  # type: ignore[arg-type]
        assert s.litellm_model_chain == ["model-a", "model-b"]

    def test_single_model_string(self) -> None:
        s = Settings(litellm_model_chain="model-a")  # type: ignore[arg-type]
        assert s.litellm_model_chain == ["model-a"]

    def test_json_list_passthrough(self) -> None:
        s = Settings(litellm_model_chain=["model-a", "model-b"])
        assert s.litellm_model_chain == ["model-a", "model-b"]


class TestModelChainValidation:
    def test_empty_chain_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one model"):
            Settings(litellm_model_chain=[])

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one model"):
            Settings(litellm_model_chain="")  # type: ignore[arg-type]

    def test_duplicate_models_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """Duplicate models in chain log a warning."""
        with caplog.at_level(logging.WARNING, logger="artifactor.config"):
            s = Settings(
                litellm_model_chain=["model-a", "model-a", "model-b"]
            )
        assert "Duplicate models in LITELLM_MODEL_CHAIN" in caplog.text
        assert "model-a" in caplog.text
        # Chain is preserved as-is (no dedup)
        assert s.litellm_model_chain == ["model-a", "model-a", "model-b"]

    def test_no_warning_without_duplicates(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="artifactor.config"):
            Settings(litellm_model_chain=["model-a", "model-b"])
        assert "Duplicate" not in caplog.text


class TestPydanticAiModels:
    def test_converts_slash_to_colon(self) -> None:
        s = Settings(
            litellm_model_chain=[
                "openai/gpt-4.1-mini",
                "anthropic/claude-sonnet-4-5-20250929",
            ]
        )
        assert s.pydantic_ai_models == [
            "openai:gpt-4.1-mini",
            "anthropic:claude-sonnet-4-5-20250929",
        ]

    def test_single_model_chain(self) -> None:
        s = Settings(litellm_model_chain=["openai/gpt-4.1-mini"])
        assert s.pydantic_ai_models == ["openai:gpt-4.1-mini"]


class TestCreateAppEngine:
    @pytest.mark.asyncio
    async def test_wal_mode_set_on_connect(
        self, tmp_path: Path,
    ) -> None:
        """WAL journal mode is set automatically on connection."""
        from sqlalchemy import text

        from artifactor.config import create_app_engine

        db_file = tmp_path / "test.db"
        engine = create_app_engine(f"sqlite:///{db_file}")

        async with engine.connect() as conn:
            row = await conn.execute(text("PRAGMA journal_mode"))
            mode = row.scalar()

        await engine.dispose()
        assert mode == "wal"

    @pytest.mark.asyncio
    async def test_url_conversion(self) -> None:
        """sqlite:/// is converted to sqlite+aiosqlite:///."""
        from artifactor.config import create_app_engine

        engine = create_app_engine("sqlite:///data/test.db")
        assert "aiosqlite" in str(engine.url)
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_already_converted_url_passthrough(self) -> None:
        """URLs already containing aiosqlite are not double-converted."""
        from artifactor.config import create_app_engine

        engine = create_app_engine(
            "sqlite+aiosqlite:///:memory:"
        )
        assert str(engine.url) == "sqlite+aiosqlite:///:memory:"
        await engine.dispose()
