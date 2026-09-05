"""Add password_hash to crew_members

Revision ID: 002_add_password_hash
Revises: 001_initial
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

revision: str = "002_add_password_hash"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column("crew_members", sa.Column("password_hash", sa.String(255), nullable=True))
        return
    conn = op.get_bind()
    cols = {column["name"] for column in sa.inspect(conn).get_columns("crew_members")}
    if "password_hash" not in cols:
        op.add_column("crew_members", sa.Column("password_hash", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("crew_members", "password_hash")
