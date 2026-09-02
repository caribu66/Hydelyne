"""Store CV-derived geographical experience on crew profiles.

Revision ID: 007_add_geographical_experience
Revises: 006_add_crew_education
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007_add_geographical_experience"
down_revision: Union[str, None] = "006_add_crew_education"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crew_members", sa.Column("geographical_experience", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("crew_members", "geographical_experience")
