from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Document as DocumentModel
from app.services.audit import audit_service
from app.services.extraction import extraction_service
from app.services.text_extraction import text_extraction_service
from app.services.upload import document_upload_service

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document operations."""

    async def create_document(
        self,
        crew_id: str,
        file_name: str,
        file_type: str,
        file_size: int,
        storage_path: str,
        classification: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> DocumentModel:
        """Create a document record in the database."""
        factory = get_session_factory()
        async with factory() as session:
            doc = DocumentModel(
                crew_member_id=crew_id,
                file_name=file_name,
                file_type=file_type,
                file_size=file_size,
                storage_type="dropbox" if storage_path.startswith("/hydenlyne/") else "local",
                storage_path=storage_path,
                dropbox_path=storage_path if storage_path.startswith("/hydenlyne/") else None,
                classification=classification,
                uploaded_by=uploaded_by,
                extraction_status="pending",
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)
            return doc

    async def get_document(self, document_id: str) -> Optional[DocumentModel]:
        """Get a document by ID."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_pending_documents(self) -> list[DocumentModel]:
        """Get all documents pending extraction."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(
                DocumentModel.extraction_status.in_(["pending", "failed", "needs_review"])
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def process_document(self, document_id: str) -> dict:
        """Process a document through the extraction pipeline.

        Args:
            document_id: UUID of the document to process.

        Returns:
            Dict with extraction results.
        """
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return {"error": "Document not found", "status": "failed"}

            doc.extraction_status = "processing"
            await session.commit()

        try:
            is_image = text_extraction_service.is_image(doc.file_type)

            # Ensure file is available locally (download from Dropbox if needed)
            local_path = doc.storage_path
            if doc.storage_type == "dropbox" and doc.dropbox_path:
                local_content = document_upload_service.get_file(doc.dropbox_path)
                if local_content is None:
                    local_content = await document_upload_service.download_from_dropbox(
                        doc.dropbox_path
                    )
                if local_content is None:
                    raise Exception(f"Could not retrieve file from Dropbox: {doc.dropbox_path}")
                # Update local_path to the cached file location
                cache_path = document_upload_service._get_local_cache_path(doc.dropbox_path)
                if cache_path:
                    local_path = str(cache_path)

            if is_image:
                extraction_result = await extraction_service.extract_from_image(
                    local_path, doc.classification or "certificate"
                )
            else:
                text = await text_extraction_service.extract_text(
                    local_path, doc.file_type
                )

                if not doc.classification:
                    classification_result = await extraction_service.classify_document(text)
                    doc.classification = classification_result.get("classification", "other")
                    async with factory() as session:
                        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
                        result = await session.execute(stmt)
                        db_doc = result.scalar_one_or_none()
                        if db_doc:
                            db_doc.classification = doc.classification
                            await session.commit()

                    extraction_result = await extraction_service.extract_document(
                        text=text,
                        document_type=doc.classification or "other",
                        is_image=False,
                    )
                else:
                    extraction_result = await extraction_service.extract_document(
                        text=text,
                        document_type=doc.classification,
                        is_image=False,
                    )

                if doc.classification == "cv":
                    from app.services.cv_processing import CVProcessingService
                    if doc.file_type == "pdf":
                        try:
                            from app.services.cv_table_extractor import (
                                extract_cv_tables,
                            )
                            table_payload = extract_cv_tables(local_path).as_extraction_payload()
                            if table_payload:
                                extraction_result = CVProcessingService.merge_table_extraction(
                                    extraction_result, table_payload
                                )
                        except Exception as exc:
                            logger.warning("Table extraction failed for %s: %s", local_path, exc)
                    extracted_training = CVProcessingService.training_from_text(text)
                    if extracted_training:
                        extraction_result["training_qualifications"] = extracted_training
                    extracted_systems = CVProcessingService.systems_from_text(text)
                    if extracted_systems:
                        extraction_result["systems"] = list(dict.fromkeys([*(extraction_result.get("systems") or []), *extracted_systems]))

            review_status, needs_review = extraction_service.determine_review_status(
                extraction_result
            )

            async with factory() as session:
                stmt = select(DocumentModel).where(DocumentModel.id == document_id)
                result = await session.execute(stmt)
                db_doc = result.scalar_one_or_none()
                if db_doc:
                    db_doc.extracted_data = extraction_result
                    db_doc.extracted_text = text if not is_image else None
                    db_doc.extraction_confidence = extraction_result.get("confidence", {})
                    db_doc.extraction_status = "needs_review" if needs_review else "extracted"
                    await session.commit()

            await audit_service.log_extraction(
                document_id=document_id,
                model_used="llama3.1:8b",
                confidence=extraction_result.get("confidence", {}),
                status="needs_review" if needs_review else "extracted",
            )

            return {
                "document_id": document_id,
                "status": "needs_review" if needs_review else "extracted",
                "classification": doc.classification,
                "confidence": extraction_result.get("confidence", {}),
            }

        except Exception as e:
            logger.error(f"Extraction failed for document {document_id}: {e}")
            async with factory() as session:
                stmt = select(DocumentModel).where(DocumentModel.id == document_id)
                result = await session.execute(stmt)
                db_doc = result.scalar_one_or_none()
                if db_doc:
                    db_doc.extraction_status = "failed"
                    await session.commit()

            await audit_service.log_extraction(
                document_id=document_id,
                model_used="llama3.1:8b",
                confidence={},
                status="failed",
            )

            return {"error": str(e), "status": "failed"}

    async def confirm_extraction(
        self,
        document_id: str,
        confirmed_data: dict,
    ) -> Optional[DocumentModel]:
        """Confirm extracted data and save to database.

        Args:
            document_id: UUID of the document.
            confirmed_data: Confirmed extraction data.

        Returns:
            Updated document or None.
        """
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return None

            doc.extracted_data = confirmed_data
            doc.extraction_status = "extracted"
            await session.commit()
            await session.refresh(doc)

            await audit_service.log_access(
                document_id=document_id,
                user_id="system",
                action="confirm_extraction",
                data_keys=list(confirmed_data.keys()),
            )

            return doc

    async def link_to_crew_member(
        self,
        document_id: str,
        crew_id: str,
    ) -> Optional[DocumentModel]:
        """Link a document to a crew member."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return None

            doc.crew_member_id = crew_id
            await session.commit()
            await session.refresh(doc)
            return doc


document_service = DocumentService()
