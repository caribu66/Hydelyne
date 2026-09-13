"""Track document extraction claims for stale-worker recovery.

Revision ID: 019_document_processing_lease
Revises: 018_document_metadata
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "019_document_processing_lease"
down_revision: str | None = "018_document_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_documents_processing_started_at",
        "documents",
        ["processing_started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_processing_started_at", table_name="documents")
    op.drop_column("documents", "processing_started_at")
