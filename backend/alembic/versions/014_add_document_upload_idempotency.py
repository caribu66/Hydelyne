"""Add idempotency key for retried document uploads.

Revision ID: 014_upload_idempotency
Revises: 013_add_cv_review_workflow
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014_upload_idempotency"
down_revision: str | None = "013_add_cv_review_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("upload_key", sa.String(length=128), nullable=True))
    op.create_index("ix_documents_upload_key", "documents", ["upload_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_documents_upload_key", table_name="documents")
    op.drop_column("documents", "upload_key")
