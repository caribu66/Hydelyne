"""Add personal information fields captured from CVs.

Revision ID: 010_add_personal_information
Revises: 009_add_training_qualifications
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "010_add_personal_information"
down_revision: Union[str, None] = "009_add_training_qualifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "crew_members", sa.Column("country_of_residence", sa.String(length=100), nullable=True)
    )
    op.add_column("crew_members", sa.Column("gender", sa.String(length=50), nullable=True))
    op.add_column("crew_members", sa.Column("languages", sa.JSON(), nullable=True))
    op.add_column("crew_members", sa.Column("flying_point", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("crew_members", "flying_point")
    op.drop_column("crew_members", "languages")
    op.drop_column("crew_members", "gender")
    op.drop_column("crew_members", "country_of_residence")
