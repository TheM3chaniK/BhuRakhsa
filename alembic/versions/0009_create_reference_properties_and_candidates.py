"""create reference_properties, reference_owners, validation_candidates, and update validation schema

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-27 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create candidate_selection_status enum
    candidate_selection_status_enum = postgresql.ENUM(
        "candidate",
        "selected",
        "rejected",
        "ambiguous",
        name="candidate_selection_status",
    )
    candidate_selection_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Add 'partial_match' to match_status enum if not present
    op.execute("ALTER TYPE match_status ADD VALUE IF NOT EXISTS 'partial_match'")

    # 3. Create reference_properties table
    op.create_table(
        "reference_properties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("source_record_id", sa.String(length=100), nullable=False),
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
        sa.Column("dataset_version", sa.String(length=50), nullable=False, server_default="1.0"),
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
        sa.UniqueConstraint("source_id", "source_record_id", name="uq_reference_property_source"),
    )
    op.create_index("ix_reference_properties_source_id", "reference_properties", ["source_id"], unique=False)
    op.create_index("ix_reference_properties_source_record_id", "reference_properties", ["source_record_id"], unique=False)
    op.create_index("ix_reference_properties_survey_number", "reference_properties", ["survey_number"], unique=False)
    op.create_index("ix_reference_properties_plot_number", "reference_properties", ["plot_number"], unique=False)
    op.create_index("ix_reference_properties_parcel_number", "reference_properties", ["parcel_number"], unique=False)
    op.create_index("ix_reference_properties_registration_number", "reference_properties", ["registration_number"], unique=False)
    op.create_index("ix_reference_properties_deed_number", "reference_properties", ["deed_number"], unique=False)
    op.create_index("ix_reference_properties_district", "reference_properties", ["district"], unique=False)
    op.create_index("ix_reference_properties_village", "reference_properties", ["village"], unique=False)

    # 4. Create reference_property_owners table
    op.create_table(
        "reference_property_owners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "reference_property_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference_properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("ownership_share", sa.String(length=50), nullable=True),
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
    op.create_index("ix_reference_property_owners_reference_property_id", "reference_property_owners", ["reference_property_id"], unique=False)
    op.create_index("ix_reference_property_owners_normalized_name", "reference_property_owners", ["normalized_name"], unique=False)

    # 5. Create validation_candidates table
    op.create_table(
        "validation_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "validation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("source_record_id", sa.String(length=100), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "selection_status",
            postgresql.ENUM(
                "candidate",
                "selected",
                "rejected",
                "ambiguous",
                name="candidate_selection_status",
                create_type=False,
            ),
            nullable=False,
            server_default="candidate",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_validation_candidates_validation_run_id", "validation_candidates", ["validation_run_id"], unique=False)

    # 6. Alter validation_runs table
    op.add_column("validation_runs", sa.Column("source_id", sa.String(length=100), nullable=True))
    op.add_column("validation_runs", sa.Column("dataset_version", sa.String(length=50), nullable=True))
    op.add_column("validation_runs", sa.Column("validator_version", sa.String(length=20), nullable=False, server_default="1.0"))

    # 7. Alter validation_results table
    op.add_column("validation_results", sa.Column("match_score", sa.Float(), nullable=False, server_default="0.0"))
    op.add_column("validation_results", sa.Column("source_id", sa.String(length=100), nullable=True))
    op.add_column("validation_results", sa.Column("source_record_id", sa.String(length=100), nullable=True))


def downgrade() -> None:
    # 1. Revert columns on validation_results
    op.drop_column("validation_results", "source_record_id")
    op.drop_column("validation_results", "source_id")
    op.drop_column("validation_results", "match_score")

    # 2. Revert columns on validation_runs
    op.drop_column("validation_runs", "validator_version")
    op.drop_column("validation_runs", "dataset_version")
    op.drop_column("validation_runs", "source_id")

    # 3. Drop validation_candidates table
    op.drop_index("ix_validation_candidates_validation_run_id", table_name="validation_candidates")
    op.drop_table("validation_candidates")

    # 4. Drop reference_property_owners table
    op.drop_index("ix_reference_property_owners_normalized_name", table_name="reference_property_owners")
    op.drop_index("ix_reference_property_owners_reference_property_id", table_name="reference_property_owners")
    op.drop_table("reference_property_owners")

    # 5. Drop reference_properties table
    op.drop_index("ix_reference_properties_village", table_name="reference_properties")
    op.drop_index("ix_reference_properties_district", table_name="reference_properties")
    op.drop_index("ix_reference_properties_deed_number", table_name="reference_properties")
    op.drop_index("ix_reference_properties_registration_number", table_name="reference_properties")
    op.drop_index("ix_reference_properties_parcel_number", table_name="reference_properties")
    op.drop_index("ix_reference_properties_plot_number", table_name="reference_properties")
    op.drop_index("ix_reference_properties_survey_number", table_name="reference_properties")
    op.drop_index("ix_reference_properties_source_record_id", table_name="reference_properties")
    op.drop_index("ix_reference_properties_source_id", table_name="reference_properties")
    op.drop_table("reference_properties")

    # 6. Drop candidate_selection_status enum
    sa.Enum(name="candidate_selection_status").drop(op.get_bind(), checkfirst=True)
