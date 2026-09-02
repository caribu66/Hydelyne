"""Widen work_history free-text fields extracted from CVs.

CV project-type and country cells routinely exceed the original 50/100 char
limits (e.g. "Offshore Construction Support / ROV Survey"), which aborted the
extraction pipeline with a value-too-long error.

Revision ID: 011_widen_work_history_fields
Revises: 010_add_personal_information
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "011_widen_work_history_fields"
down_revision: Union[str, None] = "010_add_personal_information"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "work_history",
        "project_type",
        existing_type=sa.String(length=50),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "work_history",
        "country",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "work_history",
        "country",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "work_history",
        "project_type",
        existing_type=sa.String(length=255),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
