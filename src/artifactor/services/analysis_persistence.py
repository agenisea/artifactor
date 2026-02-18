"""Persist analysis results to the database."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from artifactor.models.document import Document
from artifactor.models.entity import CodeEntityRecord
from artifactor.models.relationship import Relationship
from artifactor.repositories.document_repo import (
    SqlDocumentRepository,
)
from artifactor.repositories.entity_repo import (
    SqlEntityRepository,
)
from artifactor.repositories.protocols import (
    DocumentRepository,
    EntityRepository,
    RelationshipRepository,
)
from artifactor.repositories.relationship_repo import (
    SqlRelationshipRepository,
)
from artifactor.services.analysis_service import AnalysisResult

logger = logging.getLogger(__name__)


class AnalysisPersistenceService:
    """Atomically persist analysis outputs to the database.

    Accepts optional factory callables for repos. Defaults create
    SqlXxx repos (production). Tests can inject fakes.
    """

    def __init__(
        self,
        session_factory: Any,
        doc_repo_factory: Callable[
            [Any], DocumentRepository
        ]
        | None = None,
        entity_repo_factory: Callable[
            [Any], EntityRepository
        ]
        | None = None,
        rel_repo_factory: Callable[
            [Any], RelationshipRepository
        ]
        | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._doc_repo_factory = (
            doc_repo_factory or SqlDocumentRepository
        )
        self._entity_repo_factory = (
            entity_repo_factory or SqlEntityRepository
        )
        self._rel_repo_factory = (
            rel_repo_factory or SqlRelationshipRepository
        )

    async def persist(
        self, project_id: str, result: AnalysisResult
    ) -> None:
        """Persist sections, entities, and relationships.

        Opens a dedicated short-lived session. Cleans old data
        before inserting to support idempotent re-analysis.
        """
        async with self._session_factory() as session:
            doc_repo = self._doc_repo_factory(session)
            entity_repo = self._entity_repo_factory(session)
            rel_repo = self._rel_repo_factory(session)

            # Clean old data (idempotent re-analysis)
            await doc_repo.delete_sections(project_id)
            await entity_repo.delete_by_project(project_id)
            await rel_repo.delete_by_project(project_id)

            # Persist sections
            for section in result.sections:
                await doc_repo.upsert_section(
                    Document(
                        project_id=project_id,
                        section_name=section.section_name,
                        content=section.content,
                        confidence=section.confidence,
                    )
                )

            # Persist entities + relationships from knowledge graph
            if result.model:
                kg = result.model.knowledge_graph

                entities = [
                    CodeEntityRecord(
                        project_id=project_id,
                        name=e.name,
                        entity_type=e.entity_type,
                        file_path=e.file_path,
                        start_line=e.start_line,
                        end_line=e.end_line,
                        language=e.language or None,
                        signature=e.signature,
                    )
                    for e in kg.entities.values()
                ]
                await entity_repo.bulk_insert(entities)

                rels: list[Relationship] = []
                for rel in kg.relationships:
                    src = kg.get_entity(rel.source_id)
                    tgt = kg.get_entity(rel.target_id)
                    if src and tgt:
                        rels.append(
                            Relationship(
                                project_id=project_id,
                                source_file=src.file_path,
                                source_symbol=src.name,
                                target_file=tgt.file_path,
                                target_symbol=tgt.name,
                                relationship_type=rel.relationship_type,
                            )
                        )
                    elif src:
                        # External module target — store raw ID
                        rels.append(
                            Relationship(
                                project_id=project_id,
                                source_file=src.file_path,
                                source_symbol=src.name,
                                target_file=rel.target_id,
                                target_symbol=rel.target_id,
                                relationship_type=rel.relationship_type,
                            )
                        )
                if rels:
                    await rel_repo.bulk_insert(rels)

            await session.commit()
