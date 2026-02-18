"""SQL implementation of DocumentRepository."""

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artifactor.models.document import Document


class SqlDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_section(
        self, project_id: str, section_name: str
    ) -> Document | None:
        result = await self._session.execute(
            select(Document).where(
                Document.project_id == project_id,
                Document.section_name == section_name,
            )
        )
        return result.scalar_one_or_none()

    async def list_sections(self, project_id: str) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.section_name)
        )
        return list(result.scalars().all())

    async def upsert_section(self, document: Document) -> Document:
        existing = await self.get_section(
            document.project_id, document.section_name
        )
        if existing:
            existing.content = document.content
            existing.confidence = document.confidence
            await self._session.flush()
            return existing
        self._session.add(document)
        await self._session.flush()
        return document

    async def delete_sections(self, project_id: str) -> None:
        await self._session.execute(
            sa_delete(Document).where(Document.project_id == project_id)
        )
        await self._session.flush()
