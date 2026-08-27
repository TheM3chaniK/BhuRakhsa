"""enable postgis extension

Revision ID: 0001
Revises: 
Create Date: 2026-08-26 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable PostGIS extension."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")


def downgrade() -> None:
    """Drop PostGIS extension."""
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE;")
