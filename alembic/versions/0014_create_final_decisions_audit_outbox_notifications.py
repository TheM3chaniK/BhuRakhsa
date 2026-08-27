"""create final_decisions, audit_events, outbox_events, and notifications tables

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enums
    audit_actor_type_enum = postgresql.ENUM(
        "user",
        "system",
        name="audit_actor_type",
    )
    audit_actor_type_enum.create(op.get_bind(), checkfirst=True)

    audit_action_enum = postgresql.ENUM(
        "case_created",
        "case_submitted",
        "document_uploaded",
        "ocr_started",
        "ocr_completed",
        "ocr_failed",
        "extraction_started",
        "extraction_completed",
        "validation_started",
        "validation_completed",
        "validation_failed",
        "risk_calculated",
        "review_started",
        "review_decision_submitted",
        "proof_request_created",
        "proof_submitted",
        "proof_accepted",
        "proof_rejected",
        "proof_cancelled",
        "final_decision_created",
        "case_approved",
        "case_rejected",
        "notification_created",
        "notification_sent",
        "notification_failed",
        name="audit_action",
    )
    audit_action_enum.create(op.get_bind(), checkfirst=True)

    outbox_event_status_enum = postgresql.ENUM(
        "pending",
        "processing",
        "processed",
        "failed",
        name="outbox_event_status",
    )
    outbox_event_status_enum.create(op.get_bind(), checkfirst=True)

    notification_status_enum = postgresql.ENUM(
        "pending",
        "sent",
        "failed",
        "read",
        name="notification_status",
    )
    notification_status_enum.create(op.get_bind(), checkfirst=True)

    notification_type_enum = postgresql.ENUM(
        "proof_requested",
        "proof_submitted",
        "proof_accepted",
        "proof_rejected",
        "case_approved",
        "case_rejected",
        "case_status_changed",
        name="notification_type",
    )
    notification_type_enum.create(op.get_bind(), checkfirst=True)

    notification_channel_enum = postgresql.ENUM(
        "in_app",
        name="notification_channel",
    )
    notification_channel_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create final_decisions table
    op.create_table(
        "final_decisions",
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
            sa.ForeignKey("case_reviews.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "decision",
            postgresql.ENUM(
                "approve",
                "reject",
                "request_proof",
                name="officer_decision",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "risk_assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("risk_assessments.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.Column("property_profile_version", sa.Integer(), nullable=True),
        sa.Column(
            "decided_at",
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
    )
    op.create_index("ix_final_decisions_case_id", "final_decisions", ["case_id"], unique=True)
    op.create_index("ix_final_decisions_review_id", "final_decisions", ["review_id"], unique=False)
    op.create_index("ix_final_decisions_decided_by", "final_decisions", ["decided_by"], unique=False)

    # 3. Create audit_events table
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_type",
            postgresql.ENUM(
                "user",
                "system",
                name="audit_actor_type",
                create_type=False,
            ),
            nullable=False,
            server_default="user",
        ),
        sa.Column(
            "action",
            postgresql.ENUM(
                "case_created",
                "case_submitted",
                "document_uploaded",
                "ocr_started",
                "ocr_completed",
                "ocr_failed",
                "extraction_started",
                "extraction_completed",
                "validation_started",
                "validation_completed",
                "validation_failed",
                "risk_calculated",
                "review_started",
                "review_decision_submitted",
                "proof_request_created",
                "proof_submitted",
                "proof_accepted",
                "proof_rejected",
                "proof_cancelled",
                "final_decision_created",
                "case_approved",
                "case_rejected",
                "notification_created",
                "notification_sent",
                "notification_failed",
                name="audit_action",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("old_state", sa.String(length=50), nullable=True),
        sa.Column("new_state", sa.String(length=50), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_audit_events_case_id", "audit_events", ["case_id"], unique=False)
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"], unique=False)
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)

    # 4. Create outbox_events table
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "processing",
                "processed",
                "failed",
                name="outbox_event_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"], unique=False)
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"], unique=False)
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"], unique=False)
    op.create_index("ix_outbox_events_available_at", "outbox_events", ["available_at"], unique=False)
    op.create_index("ix_outbox_events_created_at", "outbox_events", ["created_at"], unique=False)

    # 5. Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "type",
            postgresql.ENUM(
                "proof_requested",
                "proof_submitted",
                "proof_accepted",
                "proof_rejected",
                "case_approved",
                "case_rejected",
                "case_status_changed",
                name="notification_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "channel",
            postgresql.ENUM(
                "in_app",
                name="notification_channel",
                create_type=False,
            ),
            nullable=False,
            server_default="in_app",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "sent",
                "failed",
                "read",
                name="notification_status",
                create_type=False,
            ),
            nullable=False,
            server_default="sent",
        ),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_case_id", "notifications", ["case_id"], unique=False)
    op.create_index("ix_notifications_event_id", "notifications", ["event_id"], unique=False)
    op.create_index("ix_notifications_status", "notifications", ["status"], unique=False)
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"], unique=False)
    op.create_index(
        "uq_notification_event_user",
        "notifications",
        ["event_id", "user_id", "type"],
        unique=True,
        postgresql_where=sa.text("event_id IS NOT NULL"),
    )


def downgrade() -> None:
    # 1. Drop notifications
    op.drop_index("uq_notification_event_user", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_event_id", table_name="notifications")
    op.drop_index("ix_notifications_case_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    # 2. Drop outbox_events
    op.drop_index("ix_outbox_events_created_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_available_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_table("outbox_events")

    # 3. Drop audit_events
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_id", table_name="audit_events")
    op.drop_index("ix_audit_events_case_id", table_name="audit_events")
    op.drop_table("audit_events")

    # 4. Drop final_decisions
    op.drop_index("ix_final_decisions_decided_by", table_name="final_decisions")
    op.drop_index("ix_final_decisions_review_id", table_name="final_decisions")
    op.drop_index("ix_final_decisions_case_id", table_name="final_decisions")
    op.drop_table("final_decisions")

    # 5. Drop enums
    sa.Enum(name="notification_channel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notification_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notification_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="outbox_event_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="audit_action").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="audit_actor_type").drop(op.get_bind(), checkfirst=True)
