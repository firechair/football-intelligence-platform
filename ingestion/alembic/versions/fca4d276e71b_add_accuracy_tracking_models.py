"""add_accuracy_tracking_models

Revision ID: fca4d276e71b
Revises: feb2321020e4
Create Date: 2025-11-11 20:03:21.784320

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fca4d276e71b'
down_revision: Union[str, Sequence[str], None] = 'feb2321020e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create finished_fixtures table
    op.create_table('finished_fixtures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fixture_id', sa.Integer(), nullable=False),
        sa.Column('fixture_date', sa.DateTime(), nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=True),
        sa.Column('league_name', sa.String(length=200), nullable=True),
        sa.Column('country_name', sa.String(length=100), nullable=True),
        sa.Column('home_team', sa.String(length=100), nullable=False),
        sa.Column('away_team', sa.String(length=100), nullable=False),
        sa.Column('home_score', sa.Integer(), nullable=True),
        sa.Column('away_score', sa.Integer(), nullable=True),
        sa.Column('winner', sa.String(length=10), nullable=True),
        sa.Column('halftime_home_score', sa.Integer(), nullable=True),
        sa.Column('halftime_away_score', sa.Integer(), nullable=True),
        sa.Column('total_goals', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('collected_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fixture_id'),
        sa.Index('idx_fixture_date_status', 'fixture_date', 'status'),
        sa.Index('idx_league_date_finished', 'league_id', 'fixture_date')
    )

    # Create prediction_accuracy table
    op.create_table('prediction_accuracy',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fixture_id', sa.Integer(), nullable=False),
        sa.Column('actual_home_score', sa.Integer(), nullable=True),
        sa.Column('actual_away_score', sa.Integer(), nullable=True),
        sa.Column('actual_winner', sa.String(length=10), nullable=True),
        sa.Column('actual_total_goals', sa.Integer(), nullable=True),
        sa.Column('predicted_winner_id', sa.Integer(), nullable=True),
        sa.Column('predicted_winner_name', sa.String(length=100), nullable=True),
        sa.Column('predicted_win_or_draw', sa.Boolean(), nullable=True),
        sa.Column('predicted_under_over', sa.String(length=10), nullable=True),
        sa.Column('predicted_goals_home', sa.String(length=10), nullable=True),
        sa.Column('predicted_goals_away', sa.String(length=10), nullable=True),
        sa.Column('prediction_advice', sa.Text(), nullable=True),
        sa.Column('winner_accuracy', sa.Boolean(), nullable=True),
        sa.Column('goals_accuracy', sa.Boolean(), nullable=True),
        sa.Column('total_goals_accuracy', sa.Boolean(), nullable=True),
        sa.Column('win_draw_accuracy', sa.Boolean(), nullable=True),
        sa.Column('winner_score', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('goals_score', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('overall_score', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('fixture_date', sa.DateTime(), nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=True),
        sa.Column('league_name', sa.String(length=200), nullable=True),
        sa.Column('home_team', sa.String(length=100), nullable=False),
        sa.Column('away_team', sa.String(length=100), nullable=False),
        sa.Column('evaluated_at', sa.DateTime(), nullable=True),
        sa.Column('prediction_collected_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fixture_id'),
        sa.Index('idx_fixture_date_accuracy', 'fixture_date', 'evaluated_at'),
        sa.Index('idx_league_accuracy_score', 'league_id', 'overall_score'),
        sa.Index('idx_winner_accuracy', 'winner_accuracy', 'fixture_date')
    )

    # Create accuracy_statistics table
    op.create_table('accuracy_statistics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('period_type', sa.String(length=20), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=True),
        sa.Column('league_name', sa.String(length=200), nullable=True),
        sa.Column('total_predictions', sa.Integer(), nullable=True),
        sa.Column('winner_correct', sa.Integer(), nullable=True),
        sa.Column('goals_correct', sa.Integer(), nullable=True),
        sa.Column('win_draw_correct', sa.Integer(), nullable=True),
        sa.Column('winner_accuracy_percent', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('goals_accuracy_percent', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('win_draw_accuracy_percent', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('overall_accuracy_percent', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('average_winner_score', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('average_goals_score', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('average_overall_score', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.Column('fixtures_analyzed', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_period_league_stats', 'period_type', 'league_id', 'period_start'),
        sa.Index('idx_calculated_at_stats', 'calculated_at', 'period_type')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_table('accuracy_statistics')
    op.drop_table('prediction_accuracy')
    op.drop_table('finished_fixtures')
