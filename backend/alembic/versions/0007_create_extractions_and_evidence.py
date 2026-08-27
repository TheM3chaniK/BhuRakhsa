"""create extraction_jobs, extracted_fields, and evidence tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-27 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create extraction_status enum
    extraction_status_enum = postgresql.ENUM(
        "extracted",
        "uncertain",
        "not_found",
        name="extraction_status",
    )
    extraction_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create extraction_jobs table
    op.create_table(
        "extraction_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "processing",
                "completed",
                "failed",
                name="processing_status",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_extraction_jobs_document_id", "extraction_jobs", ["document_id"], unique=False)
    op.create_index("ix_extraction_jobs_status", "extraction_jobs", ["status"], unique=False)

    # 3. Create extracted_fields table
    op.create_table(
        "extracted_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ocr_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ocr_results.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("field_value", sa.Text(), nullable=True),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "extracted",
                "uncertain",
                "not_found",
                name="extraction_status",
                create_type=False,
            ),
            nullable=False,
            server_default="extracted",
        ),
        sa.Column("extractor_version", sa.String(length=20), nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_extracted_fields_document_id", "extracted_fields", ["document_id"], unique=False)
    op.create_index("ix_extracted_fields_ocr_result_id", "extracted_fields", ["ocr_result_id"], unique=False)
    op.create_index("ix_extracted_fields_field_name", "extracted_fields", ["field_name"], unique=False)
    op.create_index("ix_extracted_fields_status", "extracted_fields", ["status"], unique=False)

    # 4. Create evidence table
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "extracted_field_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extracted_fields.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ocr_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ocr_results.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("bounding_box", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_evidence_extracted_field_id", "evidence", ["extracted_field_id"], unique=False)
    op.create_index("ix_evidence_document_id", "evidence", ["document_id"], unique=False)
    op.create_index("ix_evidence_ocr_result_id", "evidence", ["ocr_result_id"], unique=False)
    op.create_index("ix_evidence_page_number", "evidence", ["page_number"], unique=False)


def downgrade() -> None:
    # 1. Drop evidence table
    op.drop_index("ix_evidence_page_number", table_name="evidence")
    op.drop_index("ix_evidence_ocr_result_id", table_name="evidence")
    op.drop_index("ix_evidence_document_id", table_name="evidence")
    op.drop_index("ix_evidence_extracted_field_id", table_name="evidence")
    op.drop_table("evidence")

    # 2. Drop extracted_fields table
    op.drop_index("ix_extracted_fields_status", table_name="extracted_fields")
    op.drop_index("ix_extracted_fields_field_name", table_name="extracted_fields")
    op.drop_index("ix_extracted_fields_ocr_result_id", table_name="extracted_fields")
    op.drop_index("ix_extracted_fields_document_id", table_name="extracted_fields")
    op.drop_table("extracted_fields")

    # 3. Drop extraction_jobs table
    op.drop_index("ix_extraction_jobs_status", table_name="extraction_jobs")
    op.drop_index("ix_extraction_jobs_document_id", table_name="extraction_jobs")
    op.drop_table("extraction_jobs")

    # 4. Drop extraction_status enum
    sa.Enum(name="extraction_status").drop(op.get_bind(), checkfirst=True)
