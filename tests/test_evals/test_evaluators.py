"""Tests for pydantic-evals custom evaluators."""

from __future__ import annotations

from pathlib import Path

from pydantic_evals import Case, Dataset

from evals.evaluators import (
    ConfidenceAbove,
    ContainsEntities,
    OutputMatchesExpected,
    SectionComplete,
    citation_exists,
)


class TestContainsEntities:
    def test_all_present(self) -> None:
        dataset: Dataset[str, str] = Dataset(
            cases=[
                Case(
                    name="test",
                    inputs="ignored",
                    evaluators=[
                        ContainsEntities(
                            entities=["Calculator", "add"]
                        )
                    ],
                )
            ]
        )

        async def task(_: str) -> str:
            return (
                "The Calculator class has an add method."
            )

        report = dataset.evaluate_sync(task, progress=False)
        assert report.averages().assertions == 1.0

    def test_missing_entity(self) -> None:
        dataset: Dataset[str, str] = Dataset(
            cases=[
                Case(
                    name="test",
                    inputs="ignored",
                    evaluators=[
                        ContainsEntities(
                            entities=["Calculator", "Missing"]
                        )
                    ],
                )
            ]
        )

        async def task(_: str) -> str:
            return "Only Calculator here."

        report = dataset.evaluate_sync(task, progress=False)
        assert report.averages().assertions == 0.0

    def test_case_insensitive(self) -> None:
        dataset: Dataset[str, str] = Dataset(
            cases=[
                Case(
                    name="test",
                    inputs="ignored",
                    evaluators=[
                        ContainsEntities(
                            entities=["CALCULATOR"]
                        )
                    ],
                )
            ]
        )

        async def task(_: str) -> str:
            return "The calculator is here."

        report = dataset.evaluate_sync(task, progress=False)
        assert report.averages().assertions == 1.0


class TestSectionComplete:
    def test_all_sections_present(self) -> None:
        dataset: Dataset[str, str] = Dataset(
            cases=[
                Case(
                    name="test",
                    inputs="ignored",
                    evaluators=[
                        SectionComplete(
                            required=[
                                "Authentication",
                                "Data Models",
                            ]
                        )
                    ],
                )
            ]
        )

        async def task(_: str) -> str:
            return (
                "# Features\n"
                "## Authentication\nLogin.\n"
                "## Data Models\nUser.\n"
            )

        report = dataset.evaluate_sync(task, progress=False)
        assert report.averages().assertions == 1.0

    def test_missing_section(self) -> None:
        dataset: Dataset[str, str] = Dataset(
            cases=[
                Case(
                    name="test",
                    inputs="ignored",
                    evaluators=[
                        SectionComplete(
                            required=[
                                "Authentication",
                                "Security",
                            ]
                        )
                    ],
                )
            ]
        )

        async def task(_: str) -> str:
            return "## Authentication\nLogin."

        report = dataset.evaluate_sync(task, progress=False)
        assert report.averages().assertions == 0.0


class TestConfidenceAbove:
    def test_above_threshold(self) -> None:
        dataset: Dataset[str, str] = Dataset(
            cases=[
                Case(
                    name="test",
                    inputs="ignored",
                    evaluators=[
                        ConfidenceAbove(threshold=0.6)
                    ],
                )
            ]
        )

        async def task(_: str) -> str:
            return "0.85"

        report = dataset.evaluate_sync(task, progress=False)
        # ConfidenceAbove returns float score; 0.85 > 0 means pass
        case = report.cases[0]
        result = case.scores.get("ConfidenceAbove")
        assert result is not None
        assert result.value == 0.85

    def test_below_threshold(self) -> None:
        dataset: Dataset[str, str] = Dataset(
            cases=[
                Case(
                    name="test",
                    inputs="ignored",
                    evaluators=[
                        ConfidenceAbove(threshold=0.6)
                    ],
                )
            ]
        )

        async def task(_: str) -> str:
            return "0.3"

        report = dataset.evaluate_sync(task, progress=False)
        case = report.cases[0]
        result = case.scores.get("ConfidenceAbove")
        assert result is not None
        assert result.value == 0.0


class TestOutputMatchesExpected:
    def test_matches(self) -> None:
        dataset: Dataset[str, str] = Dataset(
            cases=[
                Case(
                    name="test",
                    inputs="ignored",
                    expected_output="greet",
                    evaluators=[OutputMatchesExpected()],
                )
            ]
        )

        async def task(_: str) -> str:
            return "The greet function returns a greeting."

        report = dataset.evaluate_sync(task, progress=False)
        assert report.averages().assertions == 1.0


class TestCitationExists:
    def test_valid_citation(self, tmp_path: Path) -> None:
        f = tmp_path / "main.py"
        f.write_text("line1\nline2\nline3\n")
        passed, reason = citation_exists(
            "main.py", 1, 3, tmp_path
        )
        assert passed is True

    def test_missing_file(self, tmp_path: Path) -> None:
        passed, reason = citation_exists(
            "missing.py", 1, 1, tmp_path
        )
        assert passed is False
        assert "not found" in reason.lower()

    def test_out_of_range(self, tmp_path: Path) -> None:
        f = tmp_path / "small.py"
        f.write_text("line1\n")
        passed, reason = citation_exists(
            "small.py", 1, 9999, tmp_path
        )
        assert passed is False
        assert "exceeds" in reason
