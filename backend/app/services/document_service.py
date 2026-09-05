from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select

from app.database import get_session_factory
from app.domain.fields import normalize_classification
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

    async def get_documents_by_crew(self, crew_id: str) -> list[DocumentModel]:
        """Get all documents belonging to a crew member."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.crew_member_id == crew_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def reprocess_document(self, document_id: str) -> DocumentModel:
        """Reset a document's extraction status so it's picked up again."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            if not doc:
                raise ValueError(f"Document {document_id} not found")
            doc.extraction_status = "pending"
            await session.commit()
            await session.refresh(doc)
            return doc

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
                text = await text_extraction_service.extract_text(local_path, doc.file_type)

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

                if doc.classification == "cv":
                    # CVs never go through the LLM — see
                    # CVProcessingService.extract_cv_deterministically
                    # and backend/docs/consultant-knowledge-core.md.
                    from app.services.cv_processing import CVProcessingService

                    extraction_result = CVProcessingService.extract_cv_deterministically(
                        local_path, doc.file_type, text
                    )
                else:
                    extraction_result = await extraction_service.extract_document(
                        text=text,
                        document_type=doc.classification or "other",
                        is_image=False,
                    )

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
                    if normalize_classification(db_doc.classification) == "cv":
                        from app.models import CVReview

                        review = (
                            await session.execute(
                                select(CVReview).where(CVReview.document_id == document_id)
                            )
                        ).scalar_one_or_none()
                        if review and review.status not in {"approved", "rejected"}:
                            review.proposed_data = {
                                **(review.proposed_data or {}),
                                **extraction_result,
                            }
                            review.status = "awaiting_review"
                        db_doc.extraction_status = "awaiting_review"
                    else:
                        db_doc.extraction_status = "needs_review" if needs_review else "extracted"
                    await session.commit()

            classification = normalize_classification(doc.classification)
            if classification == "certificate" and doc.crew_member_id:
                from app.services.crew import certification_service

                await certification_service.link_extracted_certificate(
                    crew_id=doc.crew_member_id,
                    document_id=document_id,
                    extracted_data=extraction_result,
                    confidence=extraction_result.get("confidence", {}),
                )

            await audit_service.log_extraction(
                document_id=document_id,
                model_used=(
                    "deterministic-cv-template"
                    if normalize_classification(doc.classification) == "cv"
                    else "llama3.1:8b"
                ),
                confidence=extraction_result.get("confidence", {}),
                status=(
                    "awaiting_review"
                    if normalize_classification(doc.classification) == "cv"
                    else "needs_review"
                    if needs_review
                    else "extracted"
                ),
            )

            return {
                "document_id": document_id,
                "status": (
                    "awaiting_review"
                    if normalize_classification(doc.classification) == "cv"
                    else "needs_review"
                    if needs_review
                    else "extracted"
                ),
                "classification": doc.classification,
                "confidence": extraction_result.get("confidence", {}),
            }

        except Exception as e:
            logger.error("Document extraction failed (%s)", type(e).__name__)
            async with factory() as session:
                stmt = select(DocumentModel).where(DocumentModel.id == document_id)
                result = await session.execute(stmt)
                db_doc = result.scalar_one_or_none()
                if db_doc:
                    db_doc.extraction_status = "failed"
                    await session.commit()

            await audit_service.log_extraction(
                document_id=document_id,
                model_used=(
                    "deterministic-cv-template"
                    if normalize_classification(doc.classification) == "cv"
                    else "llama3.1:8b"
                ),
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
            if normalize_classification(doc.classification) == "cv":
                raise ValueError("CV extraction must be confirmed through the CV review workflow")

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
