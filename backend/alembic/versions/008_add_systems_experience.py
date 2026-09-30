"""Store CV-derived systems and software experience.

Revision ID: 008_add_systems_experience
Revises: 007_add_geographical_experience
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "008_add_systems_experience"
down_revision: Union[str, None] = "007_add_geographical_experience"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crew_members", sa.Column("systems_experience", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("crew_members", "systems_experience")
