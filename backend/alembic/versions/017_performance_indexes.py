"""Add performance indexes for query optimization.

Revision ID: 017_performance_indexes
Revises: 016_vessel_assignments
"""

from alembic import op

revision = "017_performance_indexes"
down_revision = "016_vessel_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    op.create_index(
        "ix_campaign_assignments_crew_status_dates",
        "campaign_assignments",
        ["crew_member_id", "status", "start_date", "end_date"],
    )

    op.create_index(
        "ix_crew_members_full_name_trgm",
        "crew_members",
        ["full_name"],
        postgresql_using="gin",
        postgresql_ops={"full_name": "gin_trgm_ops"},
    )

    op.create_index(
        "ix_crew_members_professional_summary_trgm",
        "crew_members",
        ["professional_summary"],
        postgresql_using="gin",
        postgresql_ops={"professional_summary": "gin_trgm_ops"},
    )

    op.create_index(
        "ix_crew_members_nationality_trgm",
        "crew_members",
        ["nationality"],
        postgresql_using="gin",
        postgresql_ops={"nationality": "gin_trgm_ops"},
    )

    op.create_index(
        "ix_crew_members_email_trgm",
        "crew_members",
        ["email"],
        postgresql_using="gin",
        postgresql_ops={"email": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_crew_members_email_trgm", table_name="crew_members")
    op.drop_index("ix_crew_members_nationality_trgm", table_name="crew_members")
    op.drop_index("ix_crew_members_professional_summary_trgm", table_name="crew_members")
    op.drop_index("ix_crew_members_full_name_trgm", table_name="crew_members")
    op.drop_index("ix_campaign_assignments_crew_status_dates", table_name="campaign_assignments")
