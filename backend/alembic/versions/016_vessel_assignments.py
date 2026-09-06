"""Add persistent vessels and campaign assignments.

Revision ID: 016_vessel_assignments
Revises: 015_contractor_document_requests
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016_vessel_assignments"
down_revision: str | None = "015_contractor_document_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vessels",
        sa.Column("imo", sa.String(length=20), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mmsi", sa.String(length=50), nullable=True),
        sa.Column("callsign", sa.String(length=50), nullable=True),
        sa.Column("vessel_type", sa.String(length=100), nullable=True),
        sa.Column("flag", sa.String(length=50), nullable=True),
        sa.Column("length", sa.Float(), nullable=True),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_vessels_name", "vessels", ["name"])
    op.create_index("ix_vessels_mmsi", "vessels", ["mmsi"])
    op.create_index("ix_vessels_vessel_type", "vessels", ["vessel_type"])

    op.create_table(
        "campaign_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "crew_member_id",
            sa.String(length=36),
            sa.ForeignKey("crew_members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "vessel_imo",
            sa.String(length=20),
            sa.ForeignKey("vessels.imo", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role_on_board", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="proposed"),
        sa.Column("agreed_day_rate", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_campaign_assignments_crew_member_id", "campaign_assignments", ["crew_member_id"])
    op.create_index("ix_campaign_assignments_project_id", "campaign_assignments", ["project_id"])
    op.create_index("ix_campaign_assignments_vessel_imo", "campaign_assignments", ["vessel_imo"])
    op.create_index("ix_campaign_assignments_status", "campaign_assignments", ["status"])
    op.create_index("ix_campaign_assignments_dates", "campaign_assignments", ["start_date", "end_date"])


def downgrade() -> None:
    op.drop_table("campaign_assignments")
    op.drop_table("vessels")
