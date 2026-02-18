"""Entity relationship ORM model — calls, imports, inherits."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from artifactor.models.base import Base


class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    source_file: Mapped[str] = mapped_column(String(500))
    source_symbol: Mapped[str] = mapped_column(String(300))
    target_file: Mapped[str] = mapped_column(String(500))
    target_symbol: Mapped[str] = mapped_column(String(300))
    relationship_type: Mapped[str] = mapped_column(String(50))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "source_file": self.source_file,
            "source_symbol": self.source_symbol,
            "target_file": self.target_file,
            "target_symbol": self.target_symbol,
            "relationship_type": self.relationship_type,
        }
