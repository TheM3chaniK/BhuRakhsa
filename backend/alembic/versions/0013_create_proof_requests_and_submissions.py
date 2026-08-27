"""create proof_requests, proof_submissions, and proof_request_history tables

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-27 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enums
    proof_request_status_enum = postgresql.ENUM(
        "open",
        "submitted",
        "under_review",
        "accepted",
        "rejected",
        "cancelled",
        name="proof_request_status",
    )
    proof_request_status_enum.create(op.get_bind(), checkfirst=True)

    proof_type_enum = postgresql.ENUM(
        "ownership_document",
        "sale_deed",
        "title_document",
        "tax_receipt",
        "survey_document",
        "registration_document",
        "identity_document",
        "address_proof",
        "other",
        name="proof_type",
    )
    proof_type_enum.create(op.get_bind(), checkfirst=True)

    proof_submission_status_enum = postgresql.ENUM(
        "submitted",
        "processing",
        "processed",
        "failed",
        name="proof_submission_status",
    )
    proof_submission_status_enum.create(op.get_bind(), checkfirst=True)

    proof_request_action_enum = postgresql.ENUM(
        "created",
        "submitted",
        "processing_started",
        "processing_completed",
        "processing_failed",
        "under_review",
        "accepted",
        "rejected",
        "cancelled",
        name="proof_request_action",
    )
    proof_request_action_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create proof_requests table
    op.create_table(
        "proof_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("case_reviews.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requested_from",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "proof_type",
            postgresql.ENUM(
                "ownership_document",
                "sale_deed",
                "title_document",
                "tax_receipt",
                "survey_document",
                "registration_document",
                "identity_document",
                "address_proof",
                "other",
                name="proof_type",
                create_type=False,
            ),
            nullable=False,
            server_default="ownership_document",
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "open",
                "submitted",
                "under_review",
                "accepted",
                "rejected",
                "cancelled",
                name="proof_request_status",
                create_type=False,
            ),
            nullable=False,
            server_default="open",
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_proof_requests_case_id", "proof_requests", ["case_id"], unique=False)
    op.create_index("ix_proof_requests_review_id", "proof_requests", ["review_id"], unique=False)
    op.create_index("ix_proof_requests_requested_by", "proof_requests", ["requested_by"], unique=False)
    op.create_index("ix_proof_requests_requested_from", "proof_requests", ["requested_from"], unique=False)
    op.create_index("ix_proof_requests_status", "proof_requests", ["status"], unique=False)

    # 3. Add proof_request_id column to documents table
    op.add_column(
        "documents",
        sa.Column(
            "proof_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("proof_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_documents_proof_request_id", "documents", ["proof_request_id"], unique=False)

    # 4. Create proof_submissions table
    op.create_table(
        "proof_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "proof_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("proof_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "submitted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "submitted",
                "processing",
                "processed",
                "failed",
                name="proof_submission_status",
                create_type=False,
            ),
            nullable=False,
            server_default="submitted",
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
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
    op.create_index("ix_proof_submissions_proof_request_id", "proof_submissions", ["proof_request_id"], unique=False)
    op.create_index("ix_proof_submissions_submitted_by", "proof_submissions", ["submitted_by"], unique=False)
    op.create_index("ix_proof_submissions_document_id", "proof_submissions", ["document_id"], unique=False)
    op.create_index("ix_proof_submissions_status", "proof_submissions", ["status"], unique=False)

    # 5. Create proof_request_history table
    op.create_table(
        "proof_request_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "proof_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("proof_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_type", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column(
            "action",
            postgresql.ENUM(
                "created",
                "submitted",
                "processing_started",
                "processing_completed",
                "processing_failed",
                "under_review",
                "accepted",
                "rejected",
                "cancelled",
                name="proof_request_action",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "old_status",
            postgresql.ENUM(
                "open",
                "submitted",
                "under_review",
                "accepted",
                "rejected",
                "cancelled",
                name="proof_request_status",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "new_status",
            postgresql.ENUM(
                "open",
                "submitted",
                "under_review",
                "accepted",
                "rejected",
                "cancelled",
                name="proof_request_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_proof_request_history_proof_request_id", "proof_request_history", ["proof_request_id"], unique=False)
    op.create_index("ix_proof_request_history_actor_id", "proof_request_history", ["actor_id"], unique=False)
    op.create_index("ix_proof_request_history_created_at", "proof_request_history", ["created_at"], unique=False)


def downgrade() -> None:
    # 1. Drop proof_request_history table
    op.drop_index("ix_proof_request_history_created_at", table_name="proof_request_history")
    op.drop_index("ix_proof_request_history_actor_id", table_name="proof_request_history")
    op.drop_index("ix_proof_request_history_proof_request_id", table_name="proof_request_history")
    op.drop_table("proof_request_history")

    # 2. Drop proof_submissions table
    op.drop_index("ix_proof_submissions_status", table_name="proof_submissions")
    op.drop_index("ix_proof_submissions_document_id", table_name="proof_submissions")
    op.drop_index("ix_proof_submissions_submitted_by", table_name="proof_submissions")
    op.drop_index("ix_proof_submissions_proof_request_id", table_name="proof_submissions")
    op.drop_table("proof_submissions")

    # 3. Drop proof_request_id on documents table
    op.drop_index("ix_documents_proof_request_id", table_name="documents")
    op.drop_column("documents", "proof_request_id")

    # 4. Drop proof_requests table
    op.drop_index("ix_proof_requests_status", table_name="proof_requests")
    op.drop_index("ix_proof_requests_requested_from", table_name="proof_requests")
    op.drop_index("ix_proof_requests_requested_by", table_name="proof_requests")
    op.drop_index("ix_proof_requests_review_id", table_name="proof_requests")
    op.drop_index("ix_proof_requests_case_id", table_name="proof_requests")
    op.drop_table("proof_requests")

    # 5. Drop enums
    sa.Enum(name="proof_request_action").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="proof_submission_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="proof_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="proof_request_status").drop(op.get_bind(), checkfirst=True)
