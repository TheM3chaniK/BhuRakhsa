"""create document_processing_jobs and ocr_results tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create processing_status enum
    processing_status_enum = postgresql.ENUM(
        "queued",
        "processing",
        "completed",
        "failed",
        name="processing_status",
    )
    processing_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create document_processing_jobs table
    op.create_table(
        "document_processing_jobs",
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
    op.create_index(
        "ix_document_processing_jobs_document_id",
        "document_processing_jobs",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_processing_jobs_status",
        "document_processing_jobs",
        ["status"],
        unique=False,
    )

    # 3. Create ocr_results table
    op.create_table(
        "ocr_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_page"),
    )
    op.create_index("ix_ocr_results_document_id", "ocr_results", ["document_id"], unique=False)
    op.create_index("ix_ocr_results_page_number", "ocr_results", ["page_number"], unique=False)


def downgrade() -> None:
    # 1. Drop ocr_results table
    op.drop_index("ix_ocr_results_page_number", table_name="ocr_results")
    op.drop_index("ix_ocr_results_document_id", table_name="ocr_results")
    op.drop_table("ocr_results")

    # 2. Drop document_processing_jobs table
    op.drop_index("ix_document_processing_jobs_status", table_name="document_processing_jobs")
    op.drop_index("ix_document_processing_jobs_document_id", table_name="document_processing_jobs")
    op.drop_table("document_processing_jobs")

    # 3. Drop processing_status enum
    sa.Enum(name="processing_status").drop(op.get_bind(), checkfirst=True)
