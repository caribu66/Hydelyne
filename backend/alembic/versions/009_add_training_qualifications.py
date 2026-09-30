"""Store CV-derived training and qualifications.

Revision ID: 009_add_training_qualifications
Revises: 008_add_systems_experience
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "009_add_training_qualifications"
down_revision: Union[str, None] = "008_add_systems_experience"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crew_members", sa.Column("training_qualifications", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("crew_members", "training_qualifications")
