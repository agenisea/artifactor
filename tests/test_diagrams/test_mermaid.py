"""Tests for Mermaid syntax generators."""

from artifactor.constants import RelationshipType
from artifactor.diagrams.mermaid import (
    generate_architecture_diagram,
    generate_call_graph_diagram,
    generate_er_diagram,
    generate_sequence_diagram,
    generate_sequence_diagram_from_calls,
)
from artifactor.intelligence.knowledge_graph import (
    GraphEntity,
    GraphRelationship,
    KnowledgeGraph,
)
from artifactor.intelligence.reasoning_graph import (
    Workflow,
    WorkflowStep,
)


def _make_kg() -> KnowledgeGraph:
    kg = KnowledgeGraph()
    kg.add_entity(
        GraphEntity(
            id="main.py::greet",
            name="greet",
            entity_type="function",
            file_path="main.py",
        )
    )
    kg.add_entity(
        GraphEntity(
            id="main.py::helper",
            name="helper",
            entity_type="function",
            file_path="main.py",
        )
    )
    kg.add_entity(
        GraphEntity(
            id="models.py::User",
            name="User",
            entity_type="class",
            file_path="models.py",
        )
    )
    kg.add_entity(
        GraphEntity(
            id="models.py::Order",
            name="Order",
            entity_type="class",
            file_path="models.py",
        )
    )
    kg.add_relationship(
        GraphRelationship(
            id="call:greet:helper",
            source_id="main.py::greet",
            target_id="main.py::helper",
            relationship_type=RelationshipType.CALLS,
        )
    )
    kg.add_relationship(
        GraphRelationship(
            id="import:main:os",
            source_id="main.py",
            target_id="os",
            relationship_type=RelationshipType.IMPORTS,
        )
    )
    return kg


class TestArchitectureDiagram:
    def test_generates_mermaid(self) -> None:
        kg = _make_kg()
        result = generate_architecture_diagram(kg)
        assert result.startswith("graph TD")
        assert "greet" in result
        assert "helper" in result

    def test_empty_graph_shows_entities(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(
            GraphEntity(
                id="a.py::foo",
                name="foo",
                entity_type="function",
                file_path="a.py",
            )
        )
        result = generate_architecture_diagram(kg)
        assert "foo" in result


class TestERDiagram:
    def test_generates_er(self) -> None:
        kg = _make_kg()
        result = generate_er_diagram(kg)
        assert result.startswith("erDiagram")
        assert "User" in result
        assert "Order" in result

    def test_empty_no_classes(self) -> None:
        kg = KnowledgeGraph()
        result = generate_er_diagram(kg)
        assert result == "erDiagram"


class TestCallGraphDiagram:
    def test_generates_call_graph(self) -> None:
        kg = _make_kg()
        result = generate_call_graph_diagram(kg)
        assert "flowchart LR" in result
        assert "greet" in result

    def test_focused_on_entity(self) -> None:
        kg = _make_kg()
        result = generate_call_graph_diagram(
            kg, entity_id="main.py::greet"
        )
        assert "greet" in result
        assert "helper" in result


class TestSequenceDiagram:
    def test_generates_sequence(self) -> None:
        wf = Workflow(
            id="wf:1",
            name="checkout",
            steps=(
                WorkflowStep(0, "cart.py::add", "Add items"),
                WorkflowStep(1, "pay.py::charge", "Charge"),
                WorkflowStep(
                    2, "notify.py::send", "Notify"
                ),
            ),
        )
        result = generate_sequence_diagram(wf)
        assert "sequenceDiagram" in result
        assert "participant add" in result
        assert "charge" in result
        assert "Notify" in result

    def test_empty_workflow(self) -> None:
        wf = Workflow(id="wf:empty", name="empty")
        result = generate_sequence_diagram(wf)
        assert result == "sequenceDiagram"


class TestSequenceDiagramFromCalls:
    def test_generates_diagram(self) -> None:
        kg = _make_kg()
        result = generate_sequence_diagram_from_calls(kg)
        assert result.startswith("sequenceDiagram")
        assert "participant greet" in result
        assert "participant helper" in result
        assert "greet->>helper: calls" in result

    def test_empty_kg(self) -> None:
        kg = KnowledgeGraph()
        result = generate_sequence_diagram_from_calls(kg)
        assert result == "sequenceDiagram"

    def test_no_call_rels(self) -> None:
        """KG with only imports relationships returns empty diagram."""
        kg = KnowledgeGraph()
        kg.add_relationship(
            GraphRelationship(
                id="import:a:b",
                source_id="a.py",
                target_id="b.py",
                relationship_type=RelationshipType.IMPORTS,
            )
        )
        result = generate_sequence_diagram_from_calls(kg)
        assert result == "sequenceDiagram"
