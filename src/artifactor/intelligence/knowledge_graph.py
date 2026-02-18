"""Knowledge graph: code entities and their relationships."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from artifactor.constants import Confidence, RelationshipType
from artifactor.intelligence.value_objects import (
    Citation,
    ConfidenceScore,
)


@dataclass(frozen=True)
class GraphEntity:
    """A code entity in the knowledge graph."""

    id: str
    name: str
    entity_type: str
    file_path: str
    start_line: int = 0
    end_line: int = 0
    language: str = ""
    signature: str | None = None
    description: str | None = None
    confidence: ConfidenceScore = field(
        default_factory=lambda: ConfidenceScore(
            value=Confidence.AST_ONLY, source="ast", explanation=""
        )
    )
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True)
class GraphRelationship:
    """A typed edge between two entities."""

    id: str
    source_id: str
    target_id: str
    relationship_type: str  # calls, imports, inherits, uses
    weight: float = 1.0
    context: str | None = None
    citations: tuple[Citation, ...] = ()


@dataclass
class KnowledgeGraph:
    """Graph of discovered code entities and relationships."""

    entities: dict[str, GraphEntity] = field(
        default_factory=lambda: dict[str, GraphEntity]()
    )
    relationships: list[GraphRelationship] = field(
        default_factory=lambda: list[GraphRelationship]()
    )
    # Adjacency indices — auto-maintained, not constructor args.
    _outgoing: dict[str, list[GraphRelationship]] = field(
        init=False,
        default_factory=lambda: defaultdict[
            str, list[GraphRelationship]
        ](list),
        repr=False,
    )
    _incoming: dict[str, list[GraphRelationship]] = field(
        init=False,
        default_factory=lambda: defaultdict[
            str, list[GraphRelationship]
        ](list),
        repr=False,
    )

    def add_entity(self, entity: GraphEntity) -> None:
        """Add or replace an entity."""
        self.entities[entity.id] = entity

    def add_relationship(
        self, rel: GraphRelationship
    ) -> None:
        """Add a relationship edge and update adjacency indices."""
        self.relationships.append(rel)
        self._outgoing[rel.source_id].append(rel)
        self._incoming[rel.target_id].append(rel)

    def get_entity(self, entity_id: str) -> GraphEntity | None:
        """Retrieve entity by ID."""
        return self.entities.get(entity_id)

    def find_by_type(
        self, entity_type: str
    ) -> list[GraphEntity]:
        """Find all entities of a given type."""
        return [
            e
            for e in self.entities.values()
            if e.entity_type == entity_type
        ]

    def find_by_file(
        self, file_path: str
    ) -> list[GraphEntity]:
        """Find all entities in a given file."""
        return [
            e
            for e in self.entities.values()
            if e.file_path == file_path
        ]

    def get_callers(
        self,
        entity_id: str,
        depth: int = 1,
        _visited: set[str] | None = None,
    ) -> list[GraphEntity]:
        """Find entities that call the given entity (O(1) index lookup)."""
        if depth < 1:
            return []
        visited = _visited if _visited is not None else set[str]()
        visited.add(entity_id)
        caller_ids = {
            r.source_id
            for r in self._incoming.get(entity_id, [])
            if r.relationship_type == RelationshipType.CALLS
        }
        callers = [
            self.entities[cid]
            for cid in caller_ids
            if cid in self.entities and cid not in visited
        ]
        if depth > 1:
            for caller in list(callers):
                callers.extend(
                    self.get_callers(
                        caller.id, depth - 1, visited
                    )
                )
        return callers

    def get_callees(
        self,
        entity_id: str,
        depth: int = 1,
        _visited: set[str] | None = None,
    ) -> list[GraphEntity]:
        """Find entities called by the given entity (O(1) index lookup)."""
        if depth < 1:
            return []
        visited = _visited if _visited is not None else set[str]()
        visited.add(entity_id)
        callee_ids = {
            r.target_id
            for r in self._outgoing.get(entity_id, [])
            if r.relationship_type == RelationshipType.CALLS
        }
        callees = [
            self.entities[cid]
            for cid in callee_ids
            if cid in self.entities and cid not in visited
        ]
        if depth > 1:
            for callee in list(callees):
                callees.extend(
                    self.get_callees(
                        callee.id, depth - 1, visited
                    )
                )
        return callees

    def get_relationships_for(
        self, entity_id: str
    ) -> list[GraphRelationship]:
        """Get all relationships involving an entity (O(1) index lookup)."""
        outgoing = self._outgoing.get(entity_id, [])
        incoming = self._incoming.get(entity_id, [])
        # Deduplicate self-referential edges
        seen: set[str] = set()
        result: list[GraphRelationship] = []
        for r in [*outgoing, *incoming]:
            if r.id not in seen:
                seen.add(r.id)
                result.append(r)
        return result
