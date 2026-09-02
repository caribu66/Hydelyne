"""Persist full text recovered from source documents.

Revision ID: 005_add_document_extracted_text
Revises: 004_add_experience_months
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_add_document_extracted_text"
down_revision: Union[str, None] = "004_add_experience_months"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("extracted_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "extracted_text")
