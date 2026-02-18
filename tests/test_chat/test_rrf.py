"""Tests for Reciprocal Rank Fusion (RRF) merge strategy."""

from __future__ import annotations

from artifactor.chat.rag_pipeline import (
    VectorResult,
    _merge_results,
    _reciprocal_rank_fusion,
)
from artifactor.models.entity import CodeEntityRecord

# -- RRF scoring function --


class TestReciprocalRankFusion:
    def test_single_list_preserves_order(self) -> None:
        result = _reciprocal_rank_fusion([["a", "b", "c"]])
        assert result == ["a", "b", "c"]

    def test_overlapping_items_boosted(self) -> None:
        # "b" appears in both lists — should rank highest
        list1 = ["a", "b", "c"]
        list2 = ["b", "d", "e"]
        result = _reciprocal_rank_fusion([list1, list2])
        assert result[0] == "b"

    def test_disjoint_lists_interleaved(self) -> None:
        list1 = ["a", "b"]
        list2 = ["c", "d"]
        result = _reciprocal_rank_fusion([list1, list2])
        # Same-rank items from different lists have equal scores,
        # so first-rank items from each list come before second-rank
        assert set(result[:2]) == {"a", "c"}
        assert set(result[2:]) == {"b", "d"}

    def test_empty_lists(self) -> None:
        assert _reciprocal_rank_fusion([]) == []
        assert _reciprocal_rank_fusion([[], []]) == []

    def test_k_parameter_affects_scores(self) -> None:
        # With k=1, rank differences are amplified
        list1 = ["a", "b"]
        list2 = ["b", "a"]
        result_k1 = _reciprocal_rank_fusion([list1, list2], k=1)
        # Both have equal total score: a = 1/1 + 1/2 = 1.5, b = 1/2 + 1/1 = 1.5
        assert set(result_k1) == {"a", "b"}


# -- Merge results with RRF --


def _make_entity(
    file_path: str, start_line: int, name: str
) -> CodeEntityRecord:
    return CodeEntityRecord(
        id=f"{name}-id",
        project_id="proj1",
        name=name,
        entity_type="function",
        file_path=file_path,
        start_line=start_line,
        end_line=start_line + 5,
        language="python",
    )


def _make_vector(
    file_path: str, start_line: int, name: str, distance: float
) -> VectorResult:
    return VectorResult(
        file_path=file_path,
        symbol_name=name,
        content=f"def {name}(): ...",
        start_line=start_line,
        end_line=start_line + 5,
        distance=distance,
    )


class TestMergeResultsRRF:
    def test_no_vectors_returns_entities(self) -> None:
        entities = [
            _make_entity("a.py", 1, "foo"),
            _make_entity("b.py", 10, "bar"),
        ]
        result = _merge_results([], entities, 10)
        assert len(result) == 2

    def test_no_entities_no_vectors(self) -> None:
        result = _merge_results([], [], 10)
        assert result == []

    def test_overlap_boosts_ranking(self) -> None:
        # "bar" appears in both vector and keyword results
        vectors = [
            _make_vector("a.py", 1, "foo", 0.1),
            _make_vector("b.py", 10, "bar", 0.2),
        ]
        entities = [
            _make_entity("b.py", 10, "bar"),
            _make_entity("c.py", 20, "baz"),
        ]
        result = _merge_results(vectors, entities, 10)
        # bar should be first — it appears in both lists
        assert result[0].name == "bar"

    def test_respects_max_results(self) -> None:
        entities = [
            _make_entity(f"f{i}.py", i, f"fn{i}")
            for i in range(20)
        ]
        result = _merge_results([], entities, 5)
        assert len(result) == 5

    def test_vector_only_items_excluded(self) -> None:
        # Vector results without matching entities are skipped
        vectors = [
            _make_vector("a.py", 1, "foo", 0.1),
        ]
        entities = [
            _make_entity("b.py", 10, "bar"),
        ]
        result = _merge_results(vectors, entities, 10)
        assert len(result) == 1
        assert result[0].name == "bar"
