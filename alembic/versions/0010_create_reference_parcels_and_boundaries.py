"""create reference_parcels and reference_boundaries with PostGIS spatial indexes and extend validation

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-27 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create boundary_type and coordinate_source enums
    boundary_type_enum = postgresql.ENUM(
        "district",
        "subdivision",
        "village",
        "mouza",
        "ward",
        name="boundary_type",
    )
    boundary_type_enum.create(op.get_bind(), checkfirst=True)

    coordinate_source_enum = postgresql.ENUM(
        "document",
        "user",
        "reference_database",
        "gis",
        name="coordinate_source",
    )
    coordinate_source_enum.create(op.get_bind(), checkfirst=True)

    # 2. Add 'passed_with_limitations' to validation_status enum
    op.execute("ALTER TYPE validation_status ADD VALUE IF NOT EXISTS 'passed_with_limitations'")

    # 3. Create reference_parcels table
    op.create_table(
        "reference_parcels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "reference_property_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference_properties.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("source_record_id", sa.String(length=100), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
                spatial_index=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "centroid",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=True,
                spatial_index=False,
            ),
            nullable=True,
        ),
        sa.Column("area", sa.Float(), nullable=True),
        sa.Column("area_unit", sa.String(length=50), nullable=True, server_default="sq_meters"),
        sa.Column("srid", sa.Integer(), nullable=False, server_default="4326"),
        sa.Column("source_srid", sa.Integer(), nullable=False, server_default="4326"),
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
    )
    op.create_index("ix_reference_parcels_reference_property_id", "reference_parcels", ["reference_property_id"], unique=False)
    op.create_index("ix_reference_parcels_source_id", "reference_parcels", ["source_id"], unique=False)
    op.create_index("ix_reference_parcels_source_record_id", "reference_parcels", ["source_record_id"], unique=False)

    # 4. Create reference_boundaries table
    op.create_table(
        "reference_boundaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("source_record_id", sa.String(length=100), nullable=False),
        sa.Column(
            "boundary_type",
            postgresql.ENUM(
                "district",
                "subdivision",
                "village",
                "mouza",
                "ward",
                name="boundary_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
                spatial_index=True,
            ),
            nullable=False,
        ),
        sa.Column("source_srid", sa.Integer(), nullable=False, server_default="4326"),
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
    )
    op.create_index("ix_reference_boundaries_boundary_type", "reference_boundaries", ["boundary_type"], unique=False)
    op.create_index("ix_reference_boundaries_normalized_name", "reference_boundaries", ["normalized_name"], unique=False)
    op.create_index("ix_reference_boundaries_source_id", "reference_boundaries", ["source_id"], unique=False)
    op.create_index("ix_reference_boundaries_source_record_id", "reference_boundaries", ["source_record_id"], unique=False)

    # 5. Extend property_profiles table with location_point and coordinate_source
    op.add_column(
        "property_profiles",
        sa.Column(
            "location_point",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=True,
                spatial_index=True,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "property_profiles",
        sa.Column(
            "coordinate_source",
            postgresql.ENUM(
                "document",
                "user",
                "reference_database",
                "gis",
                name="coordinate_source",
                create_type=False,
            ),
            nullable=True,
        ),
    )

    # 6. Extend validation_results table with GIS measurement fields
    op.add_column("validation_results", sa.Column("geometry_distance_meters", sa.Float(), nullable=True))
    op.add_column("validation_results", sa.Column("geometry_area", sa.Float(), nullable=True))
    op.add_column("validation_results", sa.Column("reference_area", sa.Float(), nullable=True))
    op.add_column("validation_results", sa.Column("coordinate_latitude", sa.Float(), nullable=True))
    op.add_column("validation_results", sa.Column("coordinate_longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    # 1. Revert validation_results columns
    op.drop_column("validation_results", "coordinate_longitude")
    op.drop_column("validation_results", "coordinate_latitude")
    op.drop_column("validation_results", "reference_area")
    op.drop_column("validation_results", "geometry_area")
    op.drop_column("validation_results", "geometry_distance_meters")

    # 2. Revert property_profiles columns
    op.drop_column("property_profiles", "coordinate_source")
    op.drop_column("property_profiles", "location_point")

    # 3. Drop reference_boundaries table
    op.drop_index("ix_reference_boundaries_source_record_id", table_name="reference_boundaries")
    op.drop_index("ix_reference_boundaries_source_id", table_name="reference_boundaries")
    op.drop_index("ix_reference_boundaries_normalized_name", table_name="reference_boundaries")
    op.drop_index("ix_reference_boundaries_boundary_type", table_name="reference_boundaries")
    op.drop_table("reference_boundaries")

    # 4. Drop reference_parcels table
    op.drop_index("ix_reference_parcels_source_record_id", table_name="reference_parcels")
    op.drop_index("ix_reference_parcels_source_id", table_name="reference_parcels")
    op.drop_index("ix_reference_parcels_reference_property_id", table_name="reference_parcels")
    op.drop_table("reference_parcels")

    # 5. Drop enums
    sa.Enum(name="coordinate_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="boundary_type").drop(op.get_bind(), checkfirst=True)
