"""create case_reviews and review_history tables

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-27 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enums
    review_status_enum = postgresql.ENUM(
        "not_started",
        "in_progress",
        "completed",
        name="review_status",
    )
    review_status_enum.create(op.get_bind(), checkfirst=True)

    officer_decision_enum = postgresql.ENUM(
        "approve",
        "reject",
        "request_proof",
        name="officer_decision",
    )
    officer_decision_enum.create(op.get_bind(), checkfirst=True)

    review_action_enum = postgresql.ENUM(
        "review_started",
        "decision_submitted",
        "review_completed",
        name="review_action",
    )
    review_action_enum.create(op.get_bind(), checkfirst=True)

    # Ensure 'review_ready' in case_status enum
    op.execute("ALTER TYPE case_status ADD VALUE IF NOT EXISTS 'review_ready'")

    # 2. Create case_reviews table
    op.create_table(
        "case_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reviewer_area_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("areas.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "not_started",
                "in_progress",
                "completed",
                name="review_status",
                create_type=False,
            ),
            nullable=False,
            server_default="not_started",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decision",
            postgresql.ENUM(
                "approve",
                "reject",
                "request_proof",
                name="officer_decision",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("risk_score_at_decision", sa.Integer(), nullable=True),
        sa.Column(
            "risk_level_at_decision",
            postgresql.ENUM(
                "unknown",
                "low",
                "medium",
                "high",
                "critical",
                name="risk_level",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "risk_assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("risk_assessments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "database_validation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "gis_validation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_runs.id", ondelete="SET NULL"),
            nullable=True,
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
    op.create_index("ix_case_reviews_case_id", "case_reviews", ["case_id"], unique=False)
    op.create_index("ix_case_reviews_reviewer_id", "case_reviews", ["reviewer_id"], unique=False)
    op.create_index("ix_case_reviews_reviewer_area_id", "case_reviews", ["reviewer_area_id"], unique=False)
    op.create_index("ix_case_reviews_status", "case_reviews", ["status"], unique=False)
    op.create_index("ix_case_reviews_decision", "case_reviews", ["decision"], unique=False)
    op.create_index(
        "uq_active_case_review",
        "case_reviews",
        ["case_id"],
        unique=True,
        postgresql_where=sa.text("status != 'completed'"),
    )

    # 3. Create review_history table
    op.create_table(
        "review_history",
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
            sa.ForeignKey("case_reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "action",
            postgresql.ENUM(
                "review_started",
                "decision_submitted",
                "review_completed",
                name="review_action",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "old_status",
            postgresql.ENUM(
                "not_started",
                "in_progress",
                "completed",
                name="review_status",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "new_status",
            postgresql.ENUM(
                "not_started",
                "in_progress",
                "completed",
                name="review_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "old_decision",
            postgresql.ENUM(
                "approve",
                "reject",
                "request_proof",
                name="officer_decision",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "new_decision",
            postgresql.ENUM(
                "approve",
                "reject",
                "request_proof",
                name="officer_decision",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_review_history_case_id", "review_history", ["case_id"], unique=False)
    op.create_index("ix_review_history_review_id", "review_history", ["review_id"], unique=False)
    op.create_index("ix_review_history_actor_id", "review_history", ["actor_id"], unique=False)
    op.create_index("ix_review_history_created_at", "review_history", ["created_at"], unique=False)


def downgrade() -> None:
    # 1. Drop review_history table
    op.drop_index("ix_review_history_created_at", table_name="review_history")
    op.drop_index("ix_review_history_actor_id", table_name="review_history")
    op.drop_index("ix_review_history_review_id", table_name="review_history")
    op.drop_index("ix_review_history_case_id", table_name="review_history")
    op.drop_table("review_history")

    # 2. Drop case_reviews table
    op.drop_index("uq_active_case_review", table_name="case_reviews")
    op.drop_index("ix_case_reviews_decision", table_name="case_reviews")
    op.drop_index("ix_case_reviews_status", table_name="case_reviews")
    op.drop_index("ix_case_reviews_reviewer_area_id", table_name="case_reviews")
    op.drop_index("ix_case_reviews_reviewer_id", table_name="case_reviews")
    op.drop_index("ix_case_reviews_case_id", table_name="case_reviews")
    op.drop_table("case_reviews")

    # 3. Drop enums
    sa.Enum(name="review_action").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="officer_decision").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="review_status").drop(op.get_bind(), checkfirst=True)
