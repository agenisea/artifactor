"""Static analysis — deterministic code analysis via tree-sitter."""

from artifactor.analysis.static.analyzer import run_static_analysis
from artifactor.analysis.static.schemas import (
    APIEndpoint,
    APIEndpoints,
    APIParameter,
    ASTForest,
    CallEdge,
    CallGraph,
    CodeEntity,
    DependencyEdge,
    DependencyGraph,
    SchemaAttribute,
    SchemaEntity,
    SchemaMap,
    SchemaRelationship,
    StaticAnalysisResult,
)

__all__ = [
    "APIEndpoint",
    "APIEndpoints",
    "APIParameter",
    "ASTForest",
    "CallEdge",
    "CallGraph",
    "CodeEntity",
    "DependencyEdge",
    "DependencyGraph",
    "SchemaAttribute",
    "SchemaEntity",
    "SchemaMap",
    "SchemaRelationship",
    "StaticAnalysisResult",
    "run_static_analysis",
]
