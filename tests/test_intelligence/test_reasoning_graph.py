"""Tests for the reasoning graph module."""

from artifactor.intelligence.reasoning_graph import (
    InferredRisk,
    InferredRule,
    Purpose,
    ReasoningGraph,
    Workflow,
    WorkflowStep,
)


class TestReasoningGraph:
    def test_add_and_get_purpose(self) -> None:
        rg = ReasoningGraph()
        p = Purpose(
            entity_id="main.py::greet",
            statement="Greets users by name",
        )
        rg.add_purpose(p)
        assert rg.get_purpose("main.py::greet") == p

    def test_get_purpose_nonexistent(self) -> None:
        rg = ReasoningGraph()
        assert rg.get_purpose("missing") is None

    def test_add_and_get_rule(self) -> None:
        rg = ReasoningGraph()
        rule = InferredRule(
            id="rule:1",
            rule_text="Orders over $100 get discount",
            affected_entity_ids=("order.py::process",),
        )
        rg.add_rule(rule)
        found = rg.get_rules_for_entity("order.py::process")
        assert len(found) == 1
        assert found[0].rule_text == "Orders over $100 get discount"

    def test_get_rules_empty_for_unrelated_entity(self) -> None:
        rg = ReasoningGraph()
        rule = InferredRule(
            id="rule:1",
            rule_text="Test rule",
            affected_entity_ids=("a.py::x",),
        )
        rg.add_rule(rule)
        assert rg.get_rules_for_entity("other.py::y") == []

    def test_add_workflow(self) -> None:
        rg = ReasoningGraph()
        wf = Workflow(
            id="wf:1",
            name="checkout",
            steps=(
                WorkflowStep(0, "cart.py::add", "Add items"),
                WorkflowStep(1, "pay.py::charge", "Charge"),
            ),
        )
        rg.add_workflow(wf)
        assert len(rg.workflows) == 1
        assert rg.workflows[0].name == "checkout"
        assert len(rg.workflows[0].steps) == 2

    def test_add_and_get_risk(self) -> None:
        rg = ReasoningGraph()
        risk = InferredRisk(
            id="risk:1",
            title="SQL injection",
            risk_type="security",
            severity="high",
            file_path="handler.py",
            line=10,
        )
        rg.add_risk(risk)
        assert len(rg.risks) == 1
        assert rg.risks["risk:1"].title == "SQL injection"

    def test_get_risks_by_file(self) -> None:
        rg = ReasoningGraph()
        rg.add_risk(
            InferredRisk(
                id="risk:1",
                title="Risk A",
                file_path="a.py",
                line=1,
            )
        )
        rg.add_risk(
            InferredRisk(
                id="risk:2",
                title="Risk B",
                file_path="b.py",
                line=5,
            )
        )
        rg.add_risk(
            InferredRisk(
                id="risk:3",
                title="Risk C",
                file_path="a.py",
                line=20,
            )
        )
        a_risks = rg.get_risks_by_file("a.py")
        assert len(a_risks) == 2
        assert rg.get_risks_by_file("c.py") == []

    def test_risk_is_frozen(self) -> None:
        risk = InferredRisk(id="r:1", title="test")
        try:
            risk.title = "changed"  # type: ignore[misc]
            msg = "Should be frozen"
            raise AssertionError(msg)
        except AttributeError:
            pass

    def test_purpose_is_frozen(self) -> None:
        p = Purpose(entity_id="x", statement="test")
        try:
            p.statement = "changed"  # type: ignore[misc]
            msg = "Should be frozen"
            raise AssertionError(msg)
        except AttributeError:
            pass
