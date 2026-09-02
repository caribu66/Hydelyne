"""Store the CV's professional summary narrative on the crew profile.

Captured verbatim (uninterpreted) by the deterministic CV extractor —
no LLM involved. See backend/docs/consultant-knowledge-core.md.

Revision ID: 012_add_crew_professional_summary
Revises: 011_widen_work_history_fields
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "012_add_professional_summary"
down_revision: Union[str, None] = "011_widen_work_history_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crew_members", sa.Column("professional_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("crew_members", "professional_summary")
