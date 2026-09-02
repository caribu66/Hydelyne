from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class TextExtractionService:
    """Service for extracting text from various file formats."""

    async def extract_text(self, file_path: str, file_type: str) -> str:
        """Extract text from a file based on its type.

        Args:
            file_path: Path to the file.
            file_type: File extension (pdf, docx, jpg, etc.).

        Returns:
            Extracted text content.
        """
        if file_type in ("pdf",):
            return await self._extract_pdf(file_path)
        elif file_type in ("docx", "doc"):
            return await self._extract_docx(file_path)
        elif file_type in ("jpg", "jpeg", "png"):
            return await self._extract_image(file_path)
        elif file_type in ("eml", "msg"):
            return await self._extract_email(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    async def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF using pdfplumber."""
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF extraction failed for {file_path}: {e}")
            raise

    async def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            from docx import Document
            doc = Document(file_path)
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text for cell in row.cells if cell.text.strip()]
                    if row_text:
                        text_parts.append(" | ".join(row_text))
            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"DOCX extraction failed for {file_path}: {e}")
            raise

    async def _extract_image(self, file_path: str) -> str:
        """Extract text from image - returns path for vision model processing."""
        return f"[IMAGE:{file_path}]"

    async def _extract_email(self, file_path: str) -> str:
        """Extract text from email file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Email extraction failed for {file_path}: {e}")
            raise

    def is_image(self, file_type: str) -> bool:
        """Check if file type is an image."""
        return file_type in ("jpg", "jpeg", "png")

    def extract_text_sync(self, file_path: str, file_type: str) -> str:
        """Extract text from a file synchronously (for Celery tasks)."""
        if file_type in ("pdf",):
            return self._extract_pdf_sync(file_path)
        elif file_type in ("docx", "doc"):
            return self._extract_docx_sync(file_path)
        elif file_type in ("jpg", "jpeg", "png"):
            return f"[IMAGE:{file_path}]"
        elif file_type in ("eml", "msg"):
            return self._extract_email_sync(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def _extract_pdf_sync(self, file_path: str) -> str:
        """Extract text from PDF synchronously."""
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF extraction failed for {file_path}: {e}")
            raise

    def _extract_docx_sync(self, file_path: str) -> str:
        """Extract text from DOCX synchronously."""
        try:
            from docx import Document
            doc = Document(file_path)
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text for cell in row.cells if cell.text.strip()]
                    if row_text:
                        text_parts.append(" | ".join(row_text))
            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"DOCX extraction failed for {file_path}: {e}")
            raise

    def _extract_email_sync(self, file_path: str) -> str:
        """Extract text from email file synchronously."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Email extraction failed for {file_path}: {e}")
            raise


text_extraction_service = TextExtractionService()
