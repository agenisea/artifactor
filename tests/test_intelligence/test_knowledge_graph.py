"""Tests for the knowledge graph module."""

import time

from artifactor.intelligence.knowledge_graph import (
    GraphEntity,
    GraphRelationship,
    KnowledgeGraph,
)


def _entity(
    name: str,
    etype: str = "function",
    fpath: str = "main.py",
) -> GraphEntity:
    return GraphEntity(
        id=f"{fpath}::{name}",
        name=name,
        entity_type=etype,
        file_path=fpath,
    )


def _rel(
    source: str,
    target: str,
    rtype: str = "calls",
) -> GraphRelationship:
    return GraphRelationship(
        id=f"{rtype}:{source}:{target}",
        source_id=source,
        target_id=target,
        relationship_type=rtype,
    )


class TestKnowledgeGraph:
    def test_add_and_get_entity(self) -> None:
        kg = KnowledgeGraph()
        e = _entity("greet")
        kg.add_entity(e)
        assert kg.get_entity("main.py::greet") == e

    def test_get_nonexistent_entity(self) -> None:
        kg = KnowledgeGraph()
        assert kg.get_entity("missing") is None

    def test_find_by_type(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_entity("greet", "function"))
        kg.add_entity(_entity("User", "class"))
        funcs = kg.find_by_type("function")
        assert len(funcs) == 1
        assert funcs[0].name == "greet"

    def test_find_by_file(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_entity("a", fpath="x.py"))
        kg.add_entity(_entity("b", fpath="y.py"))
        found = kg.find_by_file("x.py")
        assert len(found) == 1
        assert found[0].name == "a"

    def test_get_callers(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_entity("main"))
        kg.add_entity(_entity("helper"))
        kg.add_relationship(
            _rel("main.py::main", "main.py::helper")
        )
        callers = kg.get_callers("main.py::helper")
        assert len(callers) == 1
        assert callers[0].name == "main"

    def test_get_callees(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_entity("main"))
        kg.add_entity(_entity("helper"))
        kg.add_relationship(
            _rel("main.py::main", "main.py::helper")
        )
        callees = kg.get_callees("main.py::main")
        assert len(callees) == 1
        assert callees[0].name == "helper"

    def test_get_relationships_for(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_entity("a"))
        kg.add_entity(_entity("b"))
        rel = _rel("main.py::a", "main.py::b")
        kg.add_relationship(rel)
        rels = kg.get_relationships_for("main.py::a")
        assert len(rels) == 1
        assert rels[0].relationship_type == "calls"

    def test_entity_is_frozen(self) -> None:
        e = _entity("greet")
        try:
            e.name = "changed"  # type: ignore[misc]
            msg = "Should be frozen"
            raise AssertionError(msg)
        except AttributeError:
            pass

    def test_get_callers_cycle_does_not_recurse(self) -> None:
        """A calls B, B calls A — should not infinite loop."""
        kg = KnowledgeGraph()
        kg.add_entity(_entity("a"))
        kg.add_entity(_entity("b"))
        kg.add_relationship(
            _rel("main.py::a", "main.py::b")
        )
        kg.add_relationship(
            _rel("main.py::b", "main.py::a")
        )
        callers = kg.get_callers("main.py::a", depth=3)
        assert len(callers) == 1
        assert callers[0].name == "b"

    def test_get_callees_cycle_does_not_recurse(self) -> None:
        """A calls B, B calls A — should not infinite loop."""
        kg = KnowledgeGraph()
        kg.add_entity(_entity("a"))
        kg.add_entity(_entity("b"))
        kg.add_relationship(
            _rel("main.py::a", "main.py::b")
        )
        kg.add_relationship(
            _rel("main.py::b", "main.py::a")
        )
        callees = kg.get_callees("main.py::a", depth=3)
        assert len(callees) == 1
        assert callees[0].name == "b"

    def test_get_callers_depth_chain(self) -> None:
        """A→B→C (no cycles), get_callers(C, 2) returns [B, A]."""
        kg = KnowledgeGraph()
        kg.add_entity(_entity("a"))
        kg.add_entity(_entity("b"))
        kg.add_entity(_entity("c"))
        kg.add_relationship(
            _rel("main.py::a", "main.py::b")
        )
        kg.add_relationship(
            _rel("main.py::b", "main.py::c")
        )
        callers = kg.get_callers("main.py::c", depth=2)
        names = {c.name for c in callers}
        assert names == {"a", "b"}

    def test_get_relationships_for_deduplicates_self_ref(
        self,
    ) -> None:
        """Self-referential edge appears once in results."""
        kg = KnowledgeGraph()
        kg.add_entity(_entity("a"))
        rel = _rel("main.py::a", "main.py::a")
        kg.add_relationship(rel)
        rels = kg.get_relationships_for("main.py::a")
        assert len(rels) == 1

    def test_adjacency_index_performance(self) -> None:
        """1K entities + 5K rels, get_callees < 10ms."""
        kg = KnowledgeGraph()
        for i in range(1000):
            kg.add_entity(
                GraphEntity(
                    id=f"f{i}::fn{i}",
                    name=f"fn{i}",
                    entity_type="function",
                    file_path=f"f{i}.py",
                )
            )
        for i in range(5000):
            src = f"f{i % 1000}::fn{i % 1000}"
            tgt = f"f{(i + 1) % 1000}::fn{(i + 1) % 1000}"
            kg.add_relationship(
                GraphRelationship(
                    id=f"call:{i}",
                    source_id=src,
                    target_id=tgt,
                    relationship_type="calls",
                )
            )
        start = time.perf_counter()
        for _ in range(100):
            kg.get_callees("f0::fn0", depth=1)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100  # 100 lookups under 100ms
