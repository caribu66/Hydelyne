"""Add contractor document-upload requests and the staff review queue.

Revision ID: 015_contractor_document_requests
Revises: 014_upload_idempotency
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "015_contractor_document_requests"
down_revision: str | None = "014_upload_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "crew_member_id",
            sa.String(length=36),
            sa.ForeignKey("crew_members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_document_requests_crew_member_id", "document_requests", ["crew_member_id"])
    op.create_index(
        "ix_document_requests_token_hash", "document_requests", ["token_hash"], unique=True
    )
    op.create_index("ix_document_requests_status", "document_requests", ["status"])
    op.create_index("ix_document_requests_expires_at", "document_requests", ["expires_at"])
    op.create_table(
        "incoming_document_reviews",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "request_id",
            sa.String(length=36),
            sa.ForeignKey("document_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unread"),
        sa.Column("claimed_by", sa.String(length=36), nullable=True),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )
    op.create_index(
        "ix_incoming_document_reviews_request_id", "incoming_document_reviews", ["request_id"]
    )
    op.create_index(
        "ix_incoming_document_reviews_document_id",
        "incoming_document_reviews",
        ["document_id"],
        unique=True,
    )
    op.create_index("ix_incoming_document_reviews_status", "incoming_document_reviews", ["status"])
    op.create_index(
        "ix_incoming_document_reviews_created_at", "incoming_document_reviews", ["created_at"]
    )


def downgrade() -> None:
    op.drop_table("incoming_document_reviews")
    op.drop_table("document_requests")
