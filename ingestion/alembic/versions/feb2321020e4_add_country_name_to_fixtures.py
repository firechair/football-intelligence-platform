"""add_country_name_to_fixtures

Revision ID: feb2321020e4
Revises: c36f894505d6
Create Date: 2025-10-03 13:19:10.673344

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'feb2321020e4'
down_revision: Union[str, Sequence[str], None] = 'c36f894505d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add country_name column to fixture_tracking_status
    op.add_column('fixture_tracking_status', 
                  sa.Column('country_name', sa.String(100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove country_name column from fixture_tracking_status
    op.drop_column('fixture_tracking_status', 'country_name')
