"""Add staged CV review and specialist publication state.

Revision ID: 013_add_cv_review_workflow
Revises: 012_add_professional_summary
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "013_add_cv_review_workflow"
down_revision: str | None = "012_add_professional_summary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "crew_members",
        sa.Column(
            "publication_status", sa.String(length=20), server_default="approved", nullable=False
        ),
    )
    op.add_column("crew_members", sa.Column("submitted_by", sa.String(length=36), nullable=True))
    op.create_index("ix_crew_members_publication_status", "crew_members", ["publication_status"])
    op.create_index("ix_crew_members_submitted_by", "crew_members", ["submitted_by"])
    op.create_table(
        "cv_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("crew_member_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="processing", nullable=False),
        sa.Column(
            "prior_publication_status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("proposed_data", sa.JSON(), nullable=True),
        sa.Column("approved_data", sa.JSON(), nullable=True),
        sa.Column("submitted_by", sa.String(length=36), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["crew_member_id"], ["crew_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index("ix_cv_reviews_crew_member_id", "cv_reviews", ["crew_member_id"])
    op.create_index("ix_cv_reviews_document_id", "cv_reviews", ["document_id"])
    op.create_index("ix_cv_reviews_reviewed_by", "cv_reviews", ["reviewed_by"])
    op.create_index("ix_cv_reviews_status", "cv_reviews", ["status"])
    op.create_index("ix_cv_reviews_submitted_by", "cv_reviews", ["submitted_by"])
    op.create_table(
        "profile_access_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("crew_member_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("actor_id", "crew_member_id", "action", "created_at"):
        op.create_index(f"ix_profile_access_events_{column}", "profile_access_events", [column])


def downgrade() -> None:
    op.drop_table("profile_access_events")
    op.drop_table("cv_reviews")
    op.drop_index("ix_crew_members_submitted_by", table_name="crew_members")
    op.drop_index("ix_crew_members_publication_status", table_name="crew_members")
    op.drop_column("crew_members", "submitted_by")
    op.drop_column("crew_members", "publication_status")
