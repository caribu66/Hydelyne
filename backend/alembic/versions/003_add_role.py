"""Add role column to crew_members for RBAC

Revision ID: 003_add_role
Revises: 002_add_password_hash
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "003_add_role"
down_revision: Union[str, None] = "002_add_password_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "crew_members",
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
    )
    op.create_index("ix_crew_members_role", "crew_members", ["role"])


def downgrade() -> None:
    op.drop_index("ix_crew_members_role", table_name="crew_members")
    op.drop_column("crew_members", "role")
