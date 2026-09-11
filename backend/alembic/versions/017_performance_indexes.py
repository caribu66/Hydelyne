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
    # Requires a privileged role on managed Postgres (RDS/GCP): CREATE
    # EXTENSION needs superuser or an explicit GRANT. IF NOT EXISTS keeps
    # re-runs safe where the extension was provisioned out of band.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # GIN/trigram builds take an exclusive lock without CONCURRENTLY, which
    # would block writes on populated tables at deploy. env.py runs each
    # revision in its own transaction, so CONCURRENTLY is legal here.
    op.create_index(
        "ix_campaign_assignments_crew_status_dates",
        "campaign_assignments",
        ["crew_member_id", "status", "start_date", "end_date"],
        if_not_exists=True,
    )

    for name, column in (
        ("ix_crew_members_full_name_trgm", "full_name"),
        ("ix_crew_members_professional_summary_trgm", "professional_summary"),
        ("ix_crew_members_nationality_trgm", "nationality"),
        ("ix_crew_members_email_trgm", "email"),
    ):
        op.create_index(
            name,
            "crew_members",
            [column],
            postgresql_using="gin",
            postgresql_ops={column: "gin_trgm_ops"},
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    for name in (
        "ix_crew_members_email_trgm",
        "ix_crew_members_nationality_trgm",
        "ix_crew_members_professional_summary_trgm",
        "ix_crew_members_full_name_trgm",
    ):
        op.drop_index(
            name,
            table_name="crew_members",
            postgresql_concurrently=True,
            if_exists=True,
        )
    op.drop_index(
        "ix_campaign_assignments_crew_status_dates",
        table_name="campaign_assignments",
        if_exists=True,
    )
