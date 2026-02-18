"""Tests for outputs base module."""

from artifactor.outputs.base import (
    SectionOutput,
    avg_confidence,
    bullet_list,
    fenced_code,
    heading,
    table,
)


def test_section_output_frozen() -> None:
    out = SectionOutput(
        title="Test",
        section_name="test",
        content="# Test",
    )
    assert out.title == "Test"
    assert out.confidence == 0.0
    assert out.citations == ()


def test_heading() -> None:
    assert heading("Hello") == "# Hello\n"
    assert heading("Sub", 2) == "## Sub\n"
    assert heading("Deep", 3) == "### Deep\n"


def test_table_empty_headers() -> None:
    assert table([], []) == ""


def test_table_with_data() -> None:
    result = table(
        ["Name", "Type"],
        [["foo", "function"], ["bar", "class"]],
    )
    assert "| Name | Type |" in result
    assert "| foo | function |" in result
    assert "| bar | class |" in result


def test_table_pads_short_rows() -> None:
    result = table(
        ["A", "B", "C"],
        [["only_a"]],
    )
    assert "| only_a |  |  |" in result


def test_bullet_list() -> None:
    result = bullet_list(["a", "b", "c"])
    assert "- a\n" in result
    assert "- c" in result


def test_bullet_list_empty() -> None:
    assert bullet_list([]) == ""


def test_fenced_code() -> None:
    result = fenced_code("print(1)", "python")
    assert result.startswith("```python\n")
    assert "print(1)" in result
    assert result.endswith("```\n")


def test_avg_confidence() -> None:
    assert avg_confidence([]) == 0.0
    assert avg_confidence([0.8, 0.6]) == 0.7
    assert avg_confidence([1.0]) == 1.0
