"""Diagram generation and rendering."""

from artifactor.diagrams.mermaid import (
    generate_architecture_diagram,
    generate_call_graph_diagram,
    generate_er_diagram,
    generate_sequence_diagram,
)
from artifactor.diagrams.renderer import (
    is_mmdc_available,
    render_mermaid,
)

__all__ = [
    "generate_architecture_diagram",
    "generate_call_graph_diagram",
    "generate_er_diagram",
    "generate_sequence_diagram",
    "is_mmdc_available",
    "render_mermaid",
]
