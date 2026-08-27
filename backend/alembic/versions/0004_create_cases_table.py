"""create cases and case_sequences tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-26 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Enums
    case_status_enum = postgresql.ENUM(
        "draft",
        "submitted",
        "processing",
        "extracted",
        "validating",
        "under_review",
        "proof_required",
        "approved",
        "rejected",
        "closed",
        "failed",
        name="case_status",
    )
    case_status_enum.create(op.get_bind(), checkfirst=True)

    risk_level_enum = postgresql.ENUM(
        "unknown",
        "low",
        "medium",
        "high",
        name="risk_level",
    )
    risk_level_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create case_sequences table
    op.create_table(
        "case_sequences",
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
    )

    # 3. Create cases table
    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_number", sa.String(length=50), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "area_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("areas.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "submitted",
                "processing",
                "extracted",
                "validating",
                "under_review",
                "proof_required",
                "approved",
                "rejected",
                "closed",
                "failed",
                name="case_status",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "risk_level",
            postgresql.ENUM(
                "unknown",
                "low",
                "medium",
                "high",
                name="risk_level",
                create_type=False,
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_cases_case_number", "cases", ["case_number"], unique=True)
    op.create_index("ix_cases_created_by", "cases", ["created_by"], unique=False)
    op.create_index("ix_cases_area_id", "cases", ["area_id"], unique=False)
    op.create_index("ix_cases_status", "cases", ["status"], unique=False)
    op.create_index("ix_cases_risk_level", "cases", ["risk_level"], unique=False)
    op.create_index("ix_cases_created_at", "cases", ["created_at"], unique=False)


def downgrade() -> None:
    # 1. Drop cases table
    op.drop_index("ix_cases_created_at", table_name="cases")
    op.drop_index("ix_cases_risk_level", table_name="cases")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_area_id", table_name="cases")
    op.drop_index("ix_cases_created_by", table_name="cases")
    op.drop_index("ix_cases_case_number", table_name="cases")
    op.drop_table("cases")

    # 2. Drop case_sequences table
    op.drop_table("case_sequences")

    # 3. Drop enums
    sa.Enum(name="risk_level").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="case_status").drop(op.get_bind(), checkfirst=True)
