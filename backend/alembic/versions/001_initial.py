"""Initial migration

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crew_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False, index=True),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("email", sa.String(255), nullable=True, index=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("emergency_contact_name", sa.String(255), nullable=True),
        sa.Column("emergency_contact_relationship", sa.String(100), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(50), nullable=True),
        sa.Column("passport_number", sa.String(50), nullable=True),
        sa.Column("passport_expiry", sa.Date, nullable=True),
        sa.Column("passport_issuing_country", sa.String(100), nullable=True),
        sa.Column("visa_type", sa.String(100), nullable=True),
        sa.Column("visa_restrictions", sa.Text, nullable=True),
        sa.Column("visa_expiry", sa.Date, nullable=True),
        sa.Column("medical_status", sa.String(50), nullable=True),
        sa.Column("medical_expiry", sa.Date, nullable=True),
        sa.Column("medical_provider", sa.String(255), nullable=True),
        sa.Column("insurance_provider", sa.String(255), nullable=True),
        sa.Column("insurance_policy_number", sa.String(100), nullable=True),
        sa.Column("insurance_coverage", sa.Text, nullable=True),
        sa.Column("insurance_expiry", sa.Date, nullable=True),
        sa.Column("availability_status", sa.String(20), default="available", index=True),
        sa.Column("availability_date", sa.Date, nullable=True),
        sa.Column("profile_completeness_score", sa.Float, nullable=True),
        sa.Column("internal_notes", sa.Text, nullable=True),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "certifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("crew_member_id", sa.String(36), sa.ForeignKey("crew_members.id"), index=True),
        sa.Column("cert_type", sa.String(50), nullable=False, index=True),
        sa.Column("cert_number", sa.String(100), nullable=True),
        sa.Column("issuing_body", sa.String(255), nullable=True),
        sa.Column("issue_date", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True, index=True),
        sa.Column("renewal_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), default="pending_verification", index=True),
        sa.Column("document_ref", sa.String(255), nullable=True),
        sa.Column("extracted_confidence", sa.Float, nullable=True),
        sa.Column("verification_status", sa.String(20), default="unverified"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "work_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("crew_member_id", sa.String(36), sa.ForeignKey("crew_members.id"), index=True),
        sa.Column("client_name", sa.String(255), nullable=True, index=True),
        sa.Column("project_name", sa.String(255), nullable=True),
        sa.Column("project_type", sa.String(50), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("country", sa.String(100), nullable=True, index=True),
        sa.Column("role", sa.String(255), nullable=True),
        sa.Column("responsibilities", sa.Text, nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("document_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_name", sa.String(255), nullable=False, index=True),
        sa.Column("project_name", sa.String(255), nullable=False),
        sa.Column("project_type", sa.String(50), index=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("water_depth", sa.String(50), nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), default="planning", index=True),
        sa.Column("crew_assigned", sa.JSON, nullable=True),
        sa.Column("requirements", sa.JSON, nullable=True),
        sa.Column("document_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("crew_member_id", sa.String(36), sa.ForeignKey("crew_members.id"), index=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("storage_type", sa.String(20), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("dropbox_path", sa.String(500), nullable=True),
        sa.Column("dropbox_revision", sa.String(100), nullable=True),
        sa.Column("classification", sa.String(50), nullable=True, index=True),
        sa.Column("classification_confidence", sa.Float, nullable=True),
        sa.Column("extraction_status", sa.String(20), default="pending", index=True),
        sa.Column("extracted_data", sa.JSON, nullable=True),
        sa.Column("extraction_confidence", sa.JSON, nullable=True),
        sa.Column("uploaded_by", sa.String(255), nullable=True),
        sa.Column("uploaded_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("version_number", sa.Integer, default=1),
        sa.Column("previous_version_id", sa.String(36), nullable=True),
        sa.Column("access_log", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("projects")
    op.drop_table("work_history")
    op.drop_table("certifications")
    op.drop_table("crew_members")
