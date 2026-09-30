"""Store education extracted from a crew member's source CV.

Revision ID: 006_add_crew_education
Revises: 005_add_document_extracted_text
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "006_add_crew_education"
down_revision: Union[str, None] = "005_add_document_extracted_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crew_members", sa.Column("education", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("crew_members", "education")
