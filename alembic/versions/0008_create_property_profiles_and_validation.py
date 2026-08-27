"""create property_profiles, owners, sources, conflicts, and validation tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-27 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Enums
    ownership_type_enum = postgresql.ENUM(
        "individual",
        "joint",
        "organization",
        "unknown",
        name="ownership_type",
    )
    ownership_type_enum.create(op.get_bind(), checkfirst=True)

    profile_status_enum = postgresql.ENUM(
        "draft",
        "extracted",
        "validation_pending",
        "validated",
        name="profile_status",
    )
    profile_status_enum.create(op.get_bind(), checkfirst=True)

    validation_type_enum = postgresql.ENUM(
        "database",
        "gis",
        name="validation_type",
    )
    validation_type_enum.create(op.get_bind(), checkfirst=True)

    validation_status_enum = postgresql.ENUM(
        "pending",
        "running",
        "passed",
        "failed",
        "error",
        name="validation_status",
    )
    validation_status_enum.create(op.get_bind(), checkfirst=True)

    match_status_enum = postgresql.ENUM(
        "match",
        "mismatch",
        "not_found",
        "not_checked",
        name="match_status",
    )
    match_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create property_profiles table
    op.create_table(
        "property_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "extracted",
                "validation_pending",
                "validated",
                name="profile_status",
                create_type=False,
            ),
            nullable=False,
            server_default="extracted",
        ),
        sa.Column("property_identifier", sa.String(length=100), nullable=True),
        sa.Column("survey_number", sa.String(length=100), nullable=True),
        sa.Column("plot_number", sa.String(length=100), nullable=True),
        sa.Column("parcel_number", sa.String(length=100), nullable=True),
        sa.Column("registration_number", sa.String(length=100), nullable=True),
        sa.Column("deed_number", sa.String(length=100), nullable=True),
        sa.Column("property_address", sa.Text(), nullable=True),
        sa.Column("district", sa.String(length=100), nullable=True),
        sa.Column("subdivision", sa.String(length=100), nullable=True),
        sa.Column("village", sa.String(length=100), nullable=True),
        sa.Column("mouza", sa.String(length=100), nullable=True),
        sa.Column("ward", sa.String(length=100), nullable=True),
        sa.Column("property_area", sa.Float(), nullable=True),
        sa.Column("area_unit", sa.String(length=50), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "parcel_geometry",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=True,
            ),
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
    op.create_index("ix_property_profiles_case_id", "property_profiles", ["case_id"], unique=True)
    op.create_index("ix_property_profiles_status", "property_profiles", ["status"], unique=False)
    op.create_index("ix_property_profiles_survey_number", "property_profiles", ["survey_number"], unique=False)
    op.create_index("ix_property_profiles_plot_number", "property_profiles", ["plot_number"], unique=False)
    op.create_index("ix_property_profiles_parcel_number", "property_profiles", ["parcel_number"], unique=False)
    op.create_index("ix_property_profiles_registration_number", "property_profiles", ["registration_number"], unique=False)

    # 3. Create property_owners table
    op.create_table(
        "property_owners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "property_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("property_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=True),
        sa.Column(
            "ownership_type",
            postgresql.ENUM(
                "individual",
                "joint",
                "organization",
                "unknown",
                name="ownership_type",
                create_type=False,
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("share", sa.String(length=50), nullable=True),
        sa.Column("share_unit", sa.String(length=50), nullable=True),
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
    op.create_index("ix_property_owners_property_profile_id", "property_owners", ["property_profile_id"], unique=False)

    # 4. Create property_field_sources table
    op.create_table(
        "property_field_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "property_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("property_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column(
            "extracted_field_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extracted_fields.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_property_field_sources_property_profile_id", "property_field_sources", ["property_profile_id"], unique=False)
    op.create_index("ix_property_field_sources_extracted_field_id", "property_field_sources", ["extracted_field_id"], unique=False)

    # 5. Create property_field_conflicts table
    op.create_table(
        "property_field_conflicts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "property_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("property_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("value_a", sa.Text(), nullable=False),
        sa.Column("value_b", sa.Text(), nullable=False),
        sa.Column("source_a", sa.Text(), nullable=True),
        sa.Column("source_b", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_property_field_conflicts_property_profile_id", "property_field_conflicts", ["property_profile_id"], unique=False)

    # 6. Create validation_runs table
    op.create_table(
        "validation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "property_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("property_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "validation_type",
            postgresql.ENUM(
                "database",
                "gis",
                name="validation_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "passed",
                "failed",
                "error",
                name="validation_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_validation_runs_property_profile_id", "validation_runs", ["property_profile_id"], unique=False)
    op.create_index("ix_validation_runs_validation_type", "validation_runs", ["validation_type"], unique=False)
    op.create_index("ix_validation_runs_status", "validation_runs", ["status"], unique=False)

    # 7. Create validation_results table
    op.create_table(
        "validation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "validation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("document_value", sa.Text(), nullable=True),
        sa.Column("reference_value", sa.Text(), nullable=True),
        sa.Column(
            "match_status",
            postgresql.ENUM(
                "match",
                "mismatch",
                "not_found",
                "not_checked",
                name="match_status",
                create_type=False,
            ),
            nullable=False,
            server_default="not_checked",
        ),
        sa.Column("mismatch_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_validation_results_validation_run_id", "validation_results", ["validation_run_id"], unique=False)
    op.create_index("ix_validation_results_field_name", "validation_results", ["field_name"], unique=False)


def downgrade() -> None:
    # 1. Drop tables in reverse order
    op.drop_index("ix_validation_results_field_name", table_name="validation_results")
    op.drop_index("ix_validation_results_validation_run_id", table_name="validation_results")
    op.drop_table("validation_results")

    op.drop_index("ix_validation_runs_status", table_name="validation_runs")
    op.drop_index("ix_validation_runs_validation_type", table_name="validation_runs")
    op.drop_index("ix_validation_runs_property_profile_id", table_name="validation_runs")
    op.drop_table("validation_runs")

    op.drop_index("ix_property_field_conflicts_property_profile_id", table_name="property_field_conflicts")
    op.drop_table("property_field_conflicts")

    op.drop_index("ix_property_field_sources_extracted_field_id", table_name="property_field_sources")
    op.drop_index("ix_property_field_sources_property_profile_id", table_name="property_field_sources")
    op.drop_table("property_field_sources")

    op.drop_index("ix_property_owners_property_profile_id", table_name="property_owners")
    op.drop_table("property_owners")

    op.drop_index("ix_property_profiles_registration_number", table_name="property_profiles")
    op.drop_index("ix_property_profiles_parcel_number", table_name="property_profiles")
    op.drop_index("ix_property_profiles_plot_number", table_name="property_profiles")
    op.drop_index("ix_property_profiles_survey_number", table_name="property_profiles")
    op.drop_index("ix_property_profiles_status", table_name="property_profiles")
    op.drop_index("ix_property_profiles_case_id", table_name="property_profiles")
    op.drop_table("property_profiles")

    # 2. Drop Enums
    sa.Enum(name="match_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="validation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="validation_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="profile_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ownership_type").drop(op.get_bind(), checkfirst=True)
