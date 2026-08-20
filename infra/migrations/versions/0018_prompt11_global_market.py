"""prompt11_global_market

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-20 16:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- assets: metadata + status lifecycle + widened asset_class ---------
    op.add_column('assets', sa.Column('name', sa.String(), nullable=True))
    op.add_column('assets', sa.Column('currency', sa.String(), nullable=True))
    op.add_column('assets', sa.Column('country', sa.String(), nullable=True))
    op.add_column('assets', sa.Column('sector', sa.String(), nullable=True))
    op.add_column('assets', sa.Column('industry', sa.String(), nullable=True))
    op.add_column('assets', sa.Column('timezone', sa.String(), nullable=True))
    op.add_column('assets', sa.Column('trading_hours', sa.JSON(), nullable=True))
    op.add_column('assets', sa.Column('status', sa.String(), nullable=False, server_default='active'))
    op.add_column('assets', sa.Column('liquidity_score', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('data_quality_score', sa.Float(), nullable=True))
    op.alter_column('assets', 'status', server_default=None)

    op.drop_constraint('ck_assets_asset_class', 'assets', type_='check')
    op.create_check_constraint(
        'ck_assets_asset_class',
        'assets',
        "asset_class IN ('crypto','forex','equity','index','commodity','etf','future','bond','option')",
    )
    op.create_check_constraint(
        'ck_assets_status',
        'assets',
        "status IN ('active','inactive','suspended','data_unavailable','low_liquidity','quarantined')",
    )

    # -- signals: opportunity classification + dedup + decay ---------------
    op.add_column('signals', sa.Column('opportunity_type', sa.String(), nullable=True))
    op.add_column('signals', sa.Column('fingerprint', sa.String(), nullable=True))
    op.add_column('signals', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_signals_fingerprint', 'signals', ['fingerprint'])

    op.drop_constraint('ck_signals_status', 'signals', type_='check')
    op.create_check_constraint(
        'ck_signals_status',
        'signals',
        "status IN ('pending','scored','risk_rejected','approved','executed','expired','invalidated')",
    )
    op.create_check_constraint(
        'ck_signals_opportunity_type',
        'signals',
        "opportunity_type IS NULL OR opportunity_type IN "
        "('breakout','breakdown','trend_continuation','reversal','mean_reversion','momentum',"
        "'volatility_expansion','volatility_compression','relative_strength','relative_weakness',"
        "'event_driven','statistical_arbitrage_candidate')",
    )

    # -- new tables ----------------------------------------------------------
    op.create_table('opportunity_clusters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('signal_ids', sa.JSON(), nullable=False),
    sa.Column('asset_ids', sa.JSON(), nullable=False),
    sa.Column('direction', sa.String(), nullable=False),
    sa.Column('factor', sa.String(), nullable=True),
    sa.Column('avg_correlation', sa.Float(), nullable=False),
    sa.Column('combined_risk', sa.Float(), nullable=False),
    sa.Column('ranking_penalty', sa.Float(), nullable=False),
    sa.CheckConstraint("direction IN ('long','short')", name='ck_opportunity_clusters_direction'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_opportunity_clusters_ts', 'opportunity_clusters', ['ts'])

    op.create_table('anomalies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('anomaly_type', sa.String(), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('reviewed', sa.Boolean(), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.CheckConstraint(
        "anomaly_type IN ('price_move','volume_spike','volatility_spike','spread_expansion',"
        "'correlation_breakdown','news_shock')",
        name='ck_anomalies_anomaly_type',
    ),
    sa.CheckConstraint("score >= 0 AND score <= 100", name='ck_anomalies_score_range'),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_anomalies_asset_id', 'anomalies', ['asset_id'])
    op.create_index('ix_anomalies_ts', 'anomalies', ['ts'])

    op.create_table('volatility_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('timeframe', sa.String(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=False),
    sa.Column('realized_vol', sa.Float(), nullable=False),
    sa.Column('percentile', sa.Float(), nullable=False),
    sa.Column('regime', sa.String(), nullable=False),
    sa.CheckConstraint(
        "event_type IN ('compression','expansion','spike','collapse')",
        name='ck_volatility_events_event_type',
    ),
    sa.CheckConstraint("regime IN ('low','normal','high','extreme')", name='ck_volatility_events_regime'),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_volatility_events_asset_id', 'volatility_events', ['asset_id'])
    op.create_index('ix_volatility_events_ts', 'volatility_events', ['ts'])

    op.create_table('watchlist_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('removal_reason', sa.String(), nullable=True),
    sa.CheckConstraint(
        "reason IN ('anomaly','news','volume','volatility','opportunity','manual')",
        name='ck_watchlist_entries_reason',
    ),
    sa.CheckConstraint("status IN ('active','removed')", name='ck_watchlist_entries_status'),
    sa.CheckConstraint(
        "removal_reason IS NULL OR removal_reason IN "
        "('opportunity_disappeared','liquidity_deterioration','data_quality_deterioration','manual')",
        name='ck_watchlist_entries_removal_reason',
    ),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('asset_id', name='uq_watchlist_entries_asset_id'),
    )


def downgrade() -> None:
    op.drop_table('watchlist_entries')
    op.drop_index('ix_volatility_events_ts', table_name='volatility_events')
    op.drop_index('ix_volatility_events_asset_id', table_name='volatility_events')
    op.drop_table('volatility_events')
    op.drop_index('ix_anomalies_ts', table_name='anomalies')
    op.drop_index('ix_anomalies_asset_id', table_name='anomalies')
    op.drop_table('anomalies')
    op.drop_index('ix_opportunity_clusters_ts', table_name='opportunity_clusters')
    op.drop_table('opportunity_clusters')

    op.drop_constraint('ck_signals_opportunity_type', 'signals', type_='check')
    op.drop_constraint('ck_signals_status', 'signals', type_='check')
    op.create_check_constraint(
        'ck_signals_status',
        'signals',
        "status IN ('pending','scored','risk_rejected','approved','executed','expired')",
    )
    op.drop_index('ix_signals_fingerprint', table_name='signals')
    op.drop_column('signals', 'expires_at')
    op.drop_column('signals', 'fingerprint')
    op.drop_column('signals', 'opportunity_type')

    op.drop_constraint('ck_assets_status', 'assets', type_='check')
    op.drop_constraint('ck_assets_asset_class', 'assets', type_='check')
    op.create_check_constraint(
        'ck_assets_asset_class',
        'assets',
        "asset_class IN ('crypto','forex','equity','index','commodity')",
    )
    op.drop_column('assets', 'data_quality_score')
    op.drop_column('assets', 'liquidity_score')
    op.drop_column('assets', 'status')
    op.drop_column('assets', 'trading_hours')
    op.drop_column('assets', 'timezone')
    op.drop_column('assets', 'industry')
    op.drop_column('assets', 'sector')
    op.drop_column('assets', 'country')
    op.drop_column('assets', 'currency')
    op.drop_column('assets', 'name')
