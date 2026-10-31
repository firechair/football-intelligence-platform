"""Add missing columns to fixture_tracking_status table

Revision ID: 3856ef5abddd
Revises: fca4d276e71b
Create Date: 2025-11-17 17:02:03.493950

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3856ef5abddd'
down_revision: Union[str, Sequence[str], None] = 'fca4d276e71b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # This migration patched a production table that had drifted from the models. On a clean
    # database the earlier migrations already created league_id and country_name.
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('fixture_tracking_status')}
    indexes = {index['name'] for index in inspector.get_indexes('fixture_tracking_status')}
    if 'league_id' not in columns:
        op.add_column('fixture_tracking_status', sa.Column('league_id', sa.Integer(), nullable=True, index=True))
    if 'country_name' not in columns:
        op.add_column('fixture_tracking_status', sa.Column('country_name', sa.String(length=100), nullable=True))

    # Create indexes for the new columns
    if 'ix_fixture_tracking_status_league_id' not in indexes:
        op.create_index('ix_fixture_tracking_status_league_id', 'fixture_tracking_status', ['league_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the added columns
    op.drop_index('ix_fixture_tracking_status_league_id', table_name='fixture_tracking_status')
    op.drop_column('fixture_tracking_status', 'country_name')
    op.drop_column('fixture_tracking_status', 'league_id')
