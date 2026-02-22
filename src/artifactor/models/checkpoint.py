"""AnalysisCheckpoint ORM model — stores per-chunk LLM analysis results."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from artifactor.models.base import Base


class AnalysisCheckpoint(Base):
    __tablename__ = "analysis_checkpoints"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    commit_sha: Mapped[str] = mapped_column(String(40), index=True)
    chunk_hash: Mapped[str] = mapped_column(String(64))
    file_path: Mapped[str] = mapped_column(String(500))
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "chunk_hash", name="uq_checkpoint_chunk"
        ),
    )
