"""Tests for the LLM analysis orchestrator."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from artifactor.analysis.llm.analyzer import run_llm_analysis
from artifactor.analysis.llm.schemas import (
    BusinessRule,
    ModuleNarrative,
    RiskIndicator,
)
from artifactor.config import Settings
from artifactor.ingestion.schemas import (
    ChunkedFiles,
    CodeChunk,
    LanguageMap,
)


def _make_inputs() -> tuple[ChunkedFiles, LanguageMap]:
    chunk = CodeChunk(
        file_path=Path("src/main.py"),
        language="python",
        chunk_type="function",
        start_line=1,
        end_line=10,
        content="def greet(name):\n    return f'Hello {name}'",
    )
    chunked = ChunkedFiles(chunks=[chunk])
    lang_map = LanguageMap(languages=[])
    return chunked, lang_map


class TestRunLlmAnalysis:
    @pytest.mark.asyncio
    async def test_successful_analysis(self) -> None:
        chunked, lang_map = _make_inputs()
        narrative = ModuleNarrative(
            file_path="src/main.py",
            purpose="Greet users",
            confidence="high",
        )
        rule = BusinessRule(
            rule_text="Greet by name",
            rule_type="validation",
        )
        risk = RiskIndicator(
            risk_type="complexity",
            severity="low",
        )

        with (
            patch(
                "artifactor.analysis.llm.analyzer.embed_chunks",
                new=AsyncMock(return_value=1),
            ),
            patch(
                "artifactor.analysis.llm.analyzer.analyze_chunk",
                new=AsyncMock(
                    return_value=(narrative, [rule], [risk])
                ),
            ),
        ):
            result = await run_llm_analysis(
                chunked, lang_map, Settings()
            )

        assert result.embeddings_stored == 1
        assert len(result.narratives) == 1
        assert result.narratives[0].purpose == "Greet users"
        assert len(result.business_rules) == 1
        assert len(result.risks) == 1

    @pytest.mark.asyncio
    async def test_embedding_failure_continues(self) -> None:
        chunked, lang_map = _make_inputs()
        narrative = ModuleNarrative(
            file_path="src/main.py",
            purpose="ok",
        )

        with (
            patch(
                "artifactor.analysis.llm.analyzer.embed_chunks",
                new=AsyncMock(
                    side_effect=Exception("embed fail")
                ),
            ),
            patch(
                "artifactor.analysis.llm.analyzer.analyze_chunk",
                new=AsyncMock(
                    return_value=(narrative, [], [])
                ),
            ),
        ):
            result = await run_llm_analysis(
                chunked, lang_map, Settings()
            )

        assert result.embeddings_stored == 0
        assert len(result.narratives) == 1

    @pytest.mark.asyncio
    async def test_empty_chunks(self) -> None:
        chunked = ChunkedFiles(chunks=[])
        lang_map = LanguageMap(languages=[])

        with patch(
            "artifactor.analysis.llm.analyzer.embed_chunks",
            new=AsyncMock(return_value=0),
        ):
            result = await run_llm_analysis(
                chunked, lang_map, Settings()
            )

        assert result.embeddings_stored == 0
        assert result.narratives == []
        assert result.business_rules == []
        assert result.risks == []

    @pytest.mark.asyncio
    async def test_checkpoint_uses_project_id_not_database_url(
        self,
    ) -> None:
        """Checkpoint writes must use the passed project_id."""
        chunked, lang_map = _make_inputs()
        narrative = ModuleNarrative(
            file_path="src/main.py", purpose="ok"
        )

        checkpoint_repo = AsyncMock()
        checkpoint_repo.get = AsyncMock(return_value=None)
        checkpoint_repo.put = AsyncMock()

        settings = Settings(database_url="sqlite:///data/test.db")

        with (
            patch(
                "artifactor.analysis.llm.analyzer.embed_chunks",
                new=AsyncMock(return_value=1),
            ),
            patch(
                "artifactor.analysis.llm.analyzer.analyze_chunk",
                new=AsyncMock(
                    return_value=(narrative, [], [])
                ),
            ),
        ):
            await run_llm_analysis(
                chunked,
                lang_map,
                settings,
                checkpoint_repo=checkpoint_repo,
                commit_sha="abc123",
                project_id="proj-42",
            )

        # Verify checkpoint was written with project_id, not database_url
        checkpoint_repo.put.assert_called_once()
        saved = checkpoint_repo.put.call_args[0][0]
        assert saved.project_id == "proj-42"
        assert saved.project_id != settings.database_url
