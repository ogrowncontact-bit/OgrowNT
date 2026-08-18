"""prompt3 pattern and opportunity confidence

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-18 21:46:15.263971

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default backfills existing rows (Phase 1-4 candles were already
    # high-quality by construction, and a neutral 50 is the honest default
    # for a score whose confidence was never computed) — dropped again after,
    # since the Python-side default (models.py) is what governs new rows.
    op.add_column('opportunity_scores', sa.Column('confidence', sa.Float(), nullable=False, server_default='50.0'))
    op.add_column('patterns', sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'))
    op.alter_column('opportunity_scores', 'confidence', server_default=None)
    op.alter_column('patterns', 'confidence', server_default=None)

    # Autogenerate doesn't diff CHECK constraint bodies, so this is hand-written:
    # widen market_events.event_type to allow 'OPPORTUNITY_CREATED'
    # (apps/worker/strategy_runner.py, Prompt 3 §26).
    op.drop_constraint('ck_market_events_event_type', 'market_events', type_='check')
    op.create_check_constraint(
        'ck_market_events_event_type',
        'market_events',
        "event_type IN ('PRICE_MOVEMENT','VOLUME_SPIKE','VOLATILITY_SPIKE',"
        "'BREAKOUT_CANDIDATE','MOMENTUM_CHANGE','TREND_CHANGE','ANOMALY',"
        "'INVALID_MARKET_DATA','OPPORTUNITY_CREATED')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_market_events_event_type', 'market_events', type_='check')
    op.create_check_constraint(
        'ck_market_events_event_type',
        'market_events',
        "event_type IN ('PRICE_MOVEMENT','VOLUME_SPIKE','VOLATILITY_SPIKE',"
        "'BREAKOUT_CANDIDATE','MOMENTUM_CHANGE','TREND_CHANGE','ANOMALY',"
        "'INVALID_MARKET_DATA')",
    )

    op.drop_column('patterns', 'confidence')
    op.drop_column('opportunity_scores', 'confidence')
