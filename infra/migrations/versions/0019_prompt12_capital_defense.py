"""prompt12_capital_defense

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-21 09:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- system_state: kill-switch state machine + capital-defense flags ---
    op.add_column('system_state', sa.Column('kill_switch_state', sa.String(), nullable=False, server_default='armed'))
    op.add_column('system_state', sa.Column('recovery_mode', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(
        'system_state', sa.Column('capital_preservation_mode', sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column('system_state', sa.Column('zero_trade_mode', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('system_state', 'kill_switch_state', server_default=None)
    op.alter_column('system_state', 'recovery_mode', server_default=None)
    op.alter_column('system_state', 'capital_preservation_mode', server_default=None)
    op.alter_column('system_state', 'zero_trade_mode', server_default=None)

    # -- risk_decisions: richer per-signal risk context ----------------------
    op.add_column('risk_decisions', sa.Column('risk_score', sa.Float(), nullable=True))
    op.add_column('risk_decisions', sa.Column('risk_state', sa.String(), nullable=True))
    op.add_column('risk_decisions', sa.Column('drawdown_state', sa.String(), nullable=True))
    op.add_column('risk_decisions', sa.Column('correlation_state', sa.String(), nullable=True))
    op.add_column('risk_decisions', sa.Column('liquidity_state', sa.String(), nullable=True))
    op.add_column('risk_decisions', sa.Column('event_state', sa.String(), nullable=True))
    op.add_column('risk_decisions', sa.Column('model_state', sa.String(), nullable=True))
    op.add_column('risk_decisions', sa.Column('data_state', sa.String(), nullable=True))
    op.add_column('risk_decisions', sa.Column('system_state', sa.String(), nullable=True))
    op.add_column('risk_decisions', sa.Column('expiration', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        'ck_risk_decisions_risk_state',
        'risk_decisions',
        "risk_state IS NULL OR risk_state IN "
        "('normal','caution','defensive','high_risk','critical','emergency','halted')",
    )

    # -- new tables ----------------------------------------------------------
    op.create_table('risk_config_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('approved_by', sa.String(), nullable=True),
    sa.Column('parameters', sa.JSON(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.CheckConstraint(
        "status IN ('pending','approved','active','superseded','rejected')",
        name='ck_risk_config_versions_status',
    ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('version', name='uq_risk_config_versions_version'),
    )

    op.create_table('risk_assessments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('risk_score', sa.Float(), nullable=False),
    sa.Column('risk_state', sa.String(), nullable=False),
    sa.Column('drawdown_state', sa.String(), nullable=True),
    sa.Column('correlation_state', sa.String(), nullable=True),
    sa.Column('liquidity_state', sa.String(), nullable=True),
    sa.Column('volatility_state', sa.String(), nullable=True),
    sa.Column('event_state', sa.String(), nullable=True),
    sa.Column('model_state', sa.String(), nullable=True),
    sa.Column('data_state', sa.String(), nullable=True),
    sa.Column('system_state', sa.String(), nullable=True),
    sa.Column('execution_state', sa.String(), nullable=True),
    sa.Column('capital_preservation_mode', sa.Boolean(), nullable=False),
    sa.Column('zero_trade_mode', sa.Boolean(), nullable=False),
    sa.Column('reasons', sa.JSON(), nullable=False),
    sa.CheckConstraint(
        "risk_state IN ('normal','caution','defensive','high_risk','critical','emergency','halted')",
        name='ck_risk_assessments_risk_state',
    ),
    sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name='ck_risk_assessments_risk_score_range'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_risk_assessments_ts', 'risk_assessments', ['ts'])


def downgrade() -> None:
    op.drop_index('ix_risk_assessments_ts', table_name='risk_assessments')
    op.drop_table('risk_assessments')
    op.drop_table('risk_config_versions')

    op.drop_constraint('ck_risk_decisions_risk_state', 'risk_decisions', type_='check')
    op.drop_column('risk_decisions', 'expiration')
    op.drop_column('risk_decisions', 'system_state')
    op.drop_column('risk_decisions', 'data_state')
    op.drop_column('risk_decisions', 'model_state')
    op.drop_column('risk_decisions', 'event_state')
    op.drop_column('risk_decisions', 'liquidity_state')
    op.drop_column('risk_decisions', 'correlation_state')
    op.drop_column('risk_decisions', 'drawdown_state')
    op.drop_column('risk_decisions', 'risk_state')
    op.drop_column('risk_decisions', 'risk_score')

    op.drop_column('system_state', 'zero_trade_mode')
    op.drop_column('system_state', 'capital_preservation_mode')
    op.drop_column('system_state', 'recovery_mode')
    op.drop_column('system_state', 'kill_switch_state')
