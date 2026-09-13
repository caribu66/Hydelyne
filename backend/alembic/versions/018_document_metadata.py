"""Persist manually supplied document compliance metadata.

Revision ID: 018_document_metadata
Revises: 017_performance_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "018_document_metadata"
down_revision: str | None = "017_performance_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("issue_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("expiry_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index("ix_documents_expiry_date", "documents", ["expiry_date"])


def downgrade() -> None:
    op.drop_index("ix_documents_expiry_date", table_name="documents")
    op.drop_column("documents", "notes")
    op.drop_column("documents", "expiry_date")
    op.drop_column("documents", "issue_date")
    op.drop_column("documents", "title")
