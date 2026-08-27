"""create mismatches, mismatch_evidence, risk_assessments, and risk_factors tables

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-27 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enums
    mismatch_type_enum = postgresql.ENUM(
        "owner_mismatch",
        "survey_number_mismatch",
        "plot_number_mismatch",
        "parcel_number_mismatch",
        "registration_number_mismatch",
        "deed_number_mismatch",
        "area_mismatch",
        "reference_gis_area_mismatch",
        "document_gis_area_mismatch",
        "district_mismatch",
        "subdivision_mismatch",
        "village_mismatch",
        "mouza_mismatch",
        "ward_mismatch",
        "parcel_not_found",
        "parcel_geometry_not_found",
        "invalid_parcel_geometry",
        "point_outside_parcel",
        "district_location_mismatch",
        "village_location_mismatch",
        "multiple_reference_candidates",
        "extraction_conflict",
        name="mismatch_type",
    )
    mismatch_type_enum.create(op.get_bind(), checkfirst=True)

    mismatch_source_enum = postgresql.ENUM(
        "extraction",
        "database",
        "gis",
        name="mismatch_source",
    )
    mismatch_source_enum.create(op.get_bind(), checkfirst=True)

    mismatch_severity_enum = postgresql.ENUM(
        "low",
        "medium",
        "high",
        "critical",
        name="mismatch_severity",
    )
    mismatch_severity_enum.create(op.get_bind(), checkfirst=True)

    risk_assessment_status_enum = postgresql.ENUM(
        "pending",
        "calculating",
        "completed",
        "failed",
        name="risk_assessment_status",
    )
    risk_assessment_status_enum.create(op.get_bind(), checkfirst=True)

    # Ensure 'critical' in risk_level
    op.execute("ALTER TYPE risk_level ADD VALUE IF NOT EXISTS 'critical'")

    # 2. Add version column to property_profiles
    op.add_column("property_profiles", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    # 3. Create mismatches table
    op.create_table(
        "mismatches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "property_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("property_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "validation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "mismatch_type",
            postgresql.ENUM(
                "owner_mismatch",
                "survey_number_mismatch",
                "plot_number_mismatch",
                "parcel_number_mismatch",
                "registration_number_mismatch",
                "deed_number_mismatch",
                "area_mismatch",
                "reference_gis_area_mismatch",
                "document_gis_area_mismatch",
                "district_mismatch",
                "subdivision_mismatch",
                "village_mismatch",
                "mouza_mismatch",
                "ward_mismatch",
                "parcel_not_found",
                "parcel_geometry_not_found",
                "invalid_parcel_geometry",
                "point_outside_parcel",
                "district_location_mismatch",
                "village_location_mismatch",
                "multiple_reference_candidates",
                "extraction_conflict",
                name="mismatch_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "mismatch_source",
            postgresql.ENUM(
                "extraction",
                "database",
                "gis",
                name="mismatch_source",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("document_value", sa.Text(), nullable=True),
        sa.Column("reference_value", sa.Text(), nullable=True),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "low",
                "medium",
                "high",
                "critical",
                name="mismatch_severity",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("rule_version", sa.String(length=20), nullable=False, server_default="1.0"),
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
    op.create_index("ix_mismatches_case_id", "mismatches", ["case_id"], unique=False)
    op.create_index("ix_mismatches_property_profile_id", "mismatches", ["property_profile_id"], unique=False)
    op.create_index("ix_mismatches_validation_run_id", "mismatches", ["validation_run_id"], unique=False)
    op.create_index("ix_mismatches_mismatch_type", "mismatches", ["mismatch_type"], unique=False)
    op.create_index("ix_mismatches_mismatch_source", "mismatches", ["mismatch_source"], unique=False)
    op.create_index("ix_mismatches_severity", "mismatches", ["severity"], unique=False)

    # 4. Create mismatch_evidence table
    op.create_table(
        "mismatch_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "mismatch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mismatches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "extracted_field_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extracted_fields.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "validation_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_results.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_mismatch_evidence_mismatch_id", "mismatch_evidence", ["mismatch_id"], unique=False)
    op.create_index("ix_mismatch_evidence_extracted_field_id", "mismatch_evidence", ["extracted_field_id"], unique=False)
    op.create_index("ix_mismatch_evidence_validation_result_id", "mismatch_evidence", ["validation_result_id"], unique=False)
    op.create_index("ix_mismatch_evidence_evidence_id", "mismatch_evidence", ["evidence_id"], unique=False)

    # 5. Create risk_assessments table
    op.create_table(
        "risk_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "property_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("property_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("property_profile_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("raw_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "risk_level",
            postgresql.ENUM(
                "unknown",
                "low",
                "medium",
                "high",
                "critical",
                name="risk_level",
                create_type=False,
            ),
            nullable=False,
            server_default="low",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "calculating",
                "completed",
                "failed",
                name="risk_assessment_status",
                create_type=False,
            ),
            nullable=False,
            server_default="completed",
        ),
        sa.Column("risk_version", sa.String(length=20), nullable=False, server_default="1.0"),
        sa.Column("severity_rule_version", sa.String(length=20), nullable=False, server_default="1.0"),
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
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "calculated_at",
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
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="chk_risk_score_bounds"),
    )
    op.create_index("ix_risk_assessments_case_id", "risk_assessments", ["case_id"], unique=False)
    op.create_index("ix_risk_assessments_property_profile_id", "risk_assessments", ["property_profile_id"], unique=False)
    op.create_index("ix_risk_assessments_status", "risk_assessments", ["status"], unique=False)

    # 6. Create risk_factors table
    op.create_table(
        "risk_factors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "risk_assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("risk_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mismatch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mismatches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("factor_code", sa.String(length=100), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "low",
                "medium",
                "high",
                "critical",
                name="mismatch_severity",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_risk_factors_risk_assessment_id", "risk_factors", ["risk_assessment_id"], unique=False)
    op.create_index("ix_risk_factors_mismatch_id", "risk_factors", ["mismatch_id"], unique=False)


def downgrade() -> None:
    # 1. Drop risk_factors table
    op.drop_index("ix_risk_factors_mismatch_id", table_name="risk_factors")
    op.drop_index("ix_risk_factors_risk_assessment_id", table_name="risk_factors")
    op.drop_table("risk_factors")

    # 2. Drop risk_assessments table
    op.drop_index("ix_risk_assessments_status", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_property_profile_id", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_case_id", table_name="risk_assessments")
    op.drop_table("risk_assessments")

    # 3. Drop mismatch_evidence table
    op.drop_index("ix_mismatch_evidence_evidence_id", table_name="mismatch_evidence")
    op.drop_index("ix_mismatch_evidence_validation_result_id", table_name="mismatch_evidence")
    op.drop_index("ix_mismatch_evidence_extracted_field_id", table_name="mismatch_evidence")
    op.drop_index("ix_mismatch_evidence_mismatch_id", table_name="mismatch_evidence")
    op.drop_table("mismatch_evidence")

    # 4. Drop mismatches table
    op.drop_index("ix_mismatches_severity", table_name="mismatches")
    op.drop_index("ix_mismatches_mismatch_source", table_name="mismatches")
    op.drop_index("ix_mismatches_mismatch_type", table_name="mismatches")
    op.drop_index("ix_mismatches_validation_run_id", table_name="mismatches")
    op.drop_index("ix_mismatches_property_profile_id", table_name="mismatches")
    op.drop_index("ix_mismatches_case_id", table_name="mismatches")
    op.drop_table("mismatches")

    # 5. Drop version column on property_profiles
    op.drop_column("property_profiles", "version")

    # 6. Drop enums
    sa.Enum(name="risk_assessment_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="mismatch_severity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="mismatch_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="mismatch_type").drop(op.get_bind(), checkfirst=True)
