"""create areas and area officer assignments tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-26 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create areas table
    op.create_table(
        "areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=True,
            ),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_areas_code", "areas", ["code"], unique=True)

    # 2. Create area_officer_assignments table
    op.create_table(
        "area_officer_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "officer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "area_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("areas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("officer_id", "area_id", name="uq_officer_area"),
    )
    op.create_index("ix_area_officer_assignments_officer_id", "area_officer_assignments", ["officer_id"], unique=False)
    op.create_index("ix_area_officer_assignments_area_id", "area_officer_assignments", ["area_id"], unique=False)


def downgrade() -> None:
    # 1. Drop area_officer_assignments table
    op.drop_index("ix_area_officer_assignments_area_id", table_name="area_officer_assignments")
    op.drop_index("ix_area_officer_assignments_officer_id", table_name="area_officer_assignments")
    op.drop_table("area_officer_assignments")

    # 2. Drop areas table
    op.drop_index("ix_areas_code", table_name="areas")
    op.drop_table("areas")
