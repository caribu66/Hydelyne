"""Store audited experience duration for crew search.

Revision ID: 004_add_experience_months
Revises: 003_add_role
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "004_add_experience_months"
down_revision: Union[str, None] = "003_add_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crew_members", sa.Column("experience_months", sa.Integer(), nullable=True))
    op.create_index("ix_crew_members_experience_months", "crew_members", ["experience_months"])


def downgrade() -> None:
    op.drop_index("ix_crew_members_experience_months", table_name="crew_members")
    op.drop_column("crew_members", "experience_months")
