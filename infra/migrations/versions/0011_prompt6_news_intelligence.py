"""prompt6 news intelligence

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-19 08:00:16.996054

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('macro_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event', sa.String(), nullable=False),
    sa.Column('country', sa.String(), nullable=False),
    sa.Column('currency', sa.String(), nullable=True),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('importance', sa.String(), nullable=False),
    sa.Column('forecast', sa.Float(), nullable=True),
    sa.Column('previous', sa.Float(), nullable=True),
    sa.Column('actual', sa.Float(), nullable=True),
    sa.Column('surprise', sa.Float(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("importance IN ('low','medium','high','critical')", name='ck_macro_events_importance'),
    sa.CheckConstraint("status IN ('scheduled','released')", name='ck_macro_events_status'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event', 'country', 'scheduled_at', name='uq_macro_events_event_country_scheduled_at')
    )
    op.create_table('event_reactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_category', sa.String(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=False),
    sa.Column('as_of', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sample_size', sa.Integer(), nullable=False),
    sa.Column('avg_reaction_pct', sa.Float(), nullable=True),
    sa.Column('positive_rate', sa.Float(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_category', 'asset_id', name='uq_event_reactions_category_asset')
    )

    # New NOT NULL columns on an already-populated table: add with a
    # server_default to backfill existing rows honestly (a neutral/"unknown"
    # value for data that predates this feature, never a fabricated real
    # one), then drop the server default so new rows go through the
    # Python-side default in models.py — same idiom as migration 0010.
    op.add_column('news_events', sa.Column('source_type', sa.String(), nullable=True))
    op.add_column('news_events', sa.Column('source_quality_score', sa.Float(), nullable=False, server_default='50.0'))
    op.add_column('news_events', sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')))
    op.add_column('news_events', sa.Column('language', sa.String(), nullable=False, server_default='en'))
    op.add_column('news_events', sa.Column('entities', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('news_events', sa.Column('novelty_score', sa.Float(), nullable=False, server_default='100.0'))
    op.add_column('news_events', sa.Column('cluster_id', sa.Integer(), nullable=True))
    op.add_column('news_events', sa.Column('source_consensus_score', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('news_events', sa.Column('has_conflicting_sources', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('news_events', sa.Column('sentiment', sa.String(), nullable=False, server_default='unknown'))
    op.add_column('news_events', sa.Column('sentiment_confidence', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('news_events', sa.Column('importance', sa.String(), nullable=False, server_default='low'))
    op.add_column('news_events', sa.Column('impact_score', sa.Float(), nullable=False, server_default='0.0'))
    op.alter_column('news_events', 'source_quality_score', server_default=None)
    op.alter_column('news_events', 'retrieved_at', server_default=None)
    op.alter_column('news_events', 'language', server_default=None)
    op.alter_column('news_events', 'entities', server_default=None)
    op.alter_column('news_events', 'novelty_score', server_default=None)
    op.alter_column('news_events', 'source_consensus_score', server_default=None)
    op.alter_column('news_events', 'has_conflicting_sources', server_default=None)
    op.alter_column('news_events', 'sentiment', server_default=None)
    op.alter_column('news_events', 'sentiment_confidence', server_default=None)
    op.alter_column('news_events', 'importance', server_default=None)
    op.alter_column('news_events', 'impact_score', server_default=None)

    op.create_foreign_key('fk_news_events_cluster_id', 'news_events', 'news_events', ['cluster_id'], ['id'])
    op.create_check_constraint('ck_news_events_importance', 'news_events', "importance IN ('low','medium','high','critical')")
    op.create_check_constraint('ck_news_events_sentiment', 'news_events', "sentiment IN ('very_bullish','bullish','neutral','bearish','very_bearish','unknown')")

    op.add_column('news_impact', sa.Column('is_direct', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column('news_impact', 'is_direct', server_default=None)

    # Autogenerate doesn't diff CHECK constraint bodies — hand-written,
    # widening news_events.category (Prompt 6 §9) and alerts.category
    # (Prompt 6 §36, a new "news" category for the 6 new alert types).
    op.drop_constraint('ck_news_events_category', 'news_events', type_='check')
    op.create_check_constraint(
        'ck_news_events_category',
        'news_events',
        "category IN ('central_bank','inflation','employment','gdp','geopolitics',"
        "'regulation','crypto','earnings','m_and_a','interest_rate','cpi','ppi','legal',"
        "'supply_chain','commodity','crypto_regulation','etf','security_breach','banking',"
        "'currency','energy','other')",
    )
    op.drop_constraint('ck_alerts_category', 'alerts', type_='check')
    op.create_check_constraint(
        'ck_alerts_category',
        'alerts',
        "category IN ('trade','risk','loss','emergency','learning','system','market','news')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_alerts_category', 'alerts', type_='check')
    op.create_check_constraint(
        'ck_alerts_category',
        'alerts',
        "category IN ('trade','risk','loss','emergency','learning','system','market')",
    )
    op.drop_constraint('ck_news_events_category', 'news_events', type_='check')
    op.create_check_constraint(
        'ck_news_events_category',
        'news_events',
        "category IN ('central_bank','inflation','employment','gdp','geopolitics',"
        "'regulation','crypto','earnings','m_and_a','other')",
    )

    op.drop_column('news_impact', 'is_direct')

    op.drop_constraint('ck_news_events_sentiment', 'news_events', type_='check')
    op.drop_constraint('ck_news_events_importance', 'news_events', type_='check')
    op.drop_constraint('fk_news_events_cluster_id', 'news_events', type_='foreignkey')
    op.drop_column('news_events', 'impact_score')
    op.drop_column('news_events', 'importance')
    op.drop_column('news_events', 'sentiment_confidence')
    op.drop_column('news_events', 'sentiment')
    op.drop_column('news_events', 'has_conflicting_sources')
    op.drop_column('news_events', 'source_consensus_score')
    op.drop_column('news_events', 'cluster_id')
    op.drop_column('news_events', 'novelty_score')
    op.drop_column('news_events', 'entities')
    op.drop_column('news_events', 'language')
    op.drop_column('news_events', 'retrieved_at')
    op.drop_column('news_events', 'source_quality_score')
    op.drop_column('news_events', 'source_type')

    op.drop_table('event_reactions')
    op.drop_table('macro_events')
