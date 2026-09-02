"""Add password_hash to crew_members

Revision ID: 002_add_password_hash
Revises: 001_initial
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_add_password_hash"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = conn.exec_driver_sql(
        "SELECT column_name FROM information_schema.columns WHERE table_name='crew_members' AND column_name='password_hash'"
    ).fetchall()
    if not cols:
        op.add_column("crew_members", sa.Column("password_hash", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("crew_members", "password_hash")
