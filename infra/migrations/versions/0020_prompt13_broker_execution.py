"""prompt13_broker_execution

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-21 09:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- assets: instrument precision (§60-62) --------------------------
    op.add_column('assets', sa.Column('tick_size', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('step_size', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('min_quantity', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('min_notional', sa.Float(), nullable=True))

    # -- new tables --------------------------------------------------------
    op.create_table(
        'brokers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('paper','sandbox','live')", name='ck_brokers_kind'),
        sa.CheckConstraint("status IN ('active','inactive')", name='ck_brokers_status'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_brokers_name'),
    )
    op.alter_column('brokers', 'status', server_default=None)
    op.alter_column('brokers', 'is_default', server_default=None)

    op.create_table(
        'broker_health_checks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broker_id', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('detail', sa.JSON(), nullable=False),
        sa.CheckConstraint("state IN ('healthy','degraded','unavailable','quarantined')", name='ck_broker_health_checks_state'),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('broker_health_checks', 'error_count', server_default=None)
    op.create_index('ix_broker_health_checks_ts', 'broker_health_checks', ['ts'])

    op.create_table(
        'account_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broker_id', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('balance', sa.Float(), nullable=False),
        sa.Column('available_balance', sa.Float(), nullable=False),
        sa.Column('equity', sa.Float(), nullable=False),
        sa.Column('margin', sa.Float(), nullable=False, server_default='0'),
        sa.Column('margin_used', sa.Float(), nullable=False, server_default='0'),
        sa.Column('margin_available', sa.Float(), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(), nullable=False, server_default='USD'),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('account_snapshots', 'margin', server_default=None)
    op.alter_column('account_snapshots', 'margin_used', server_default=None)
    op.alter_column('account_snapshots', 'margin_available', server_default=None)
    op.alter_column('account_snapshots', 'currency', server_default=None)
    op.create_index('ix_account_snapshots_ts', 'account_snapshots', ['ts'])

    op.create_table(
        'broker_position_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broker_id', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('average_price', sa.Float(), nullable=False),
        sa.Column('mark_price', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl', sa.Float(), nullable=True),
        sa.Column('realized_pnl', sa.Float(), nullable=True),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('leverage', sa.Float(), nullable=False, server_default='1'),
        sa.Column('margin', sa.Float(), nullable=False, server_default='0'),
        sa.CheckConstraint("side IN ('long','short')", name='ck_broker_position_snapshots_side'),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('broker_position_snapshots', 'leverage', server_default=None)
    op.alter_column('broker_position_snapshots', 'margin', server_default=None)
    op.create_index('ix_broker_position_snapshots_ts', 'broker_position_snapshots', ['ts'])

    op.create_table(
        'executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('broker_order_id', sa.String(), nullable=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('fee', sa.Float(), nullable=False, server_default='0'),
        sa.Column('fee_currency', sa.String(), nullable=False, server_default='USD'),
        sa.Column('slippage_bps', sa.Float(), nullable=True),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('liquidity', sa.String(), nullable=False, server_default='taker'),
        sa.Column('execution_mode', sa.String(), nullable=False, server_default='paper'),
        sa.CheckConstraint("side IN ('buy','sell')", name='ck_executions_side'),
        sa.CheckConstraint("liquidity IN ('maker','taker')", name='ck_executions_liquidity'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('executions', 'fee', server_default=None)
    op.alter_column('executions', 'fee_currency', server_default=None)
    op.alter_column('executions', 'liquidity', server_default=None)
    op.alter_column('executions', 'execution_mode', server_default=None)
    op.create_index('ix_executions_order_id', 'executions', ['order_id'])

    op.create_table(
        'broker_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broker_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload_hash', sa.String(), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('detail', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('broker_id', 'event_type', 'payload_hash', name='uq_broker_events_dedup'),
    )
    op.alter_column('broker_events', 'processed', server_default=None)

    op.create_table(
        'reconciliation_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broker_id', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ok', sa.Boolean(), nullable=False),
        sa.Column('violations', sa.JSON(), nullable=False),
        sa.Column('position_mismatches', sa.JSON(), nullable=False),
        sa.Column('order_mismatches', sa.JSON(), nullable=False),
        sa.Column('balance_diff', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reconciliation_runs_ts', 'reconciliation_runs', ['ts'])

    # -- orders: broker/execution-mode/traceability/order-type fields ------
    op.add_column('orders', sa.Column('broker_id', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('execution_mode', sa.String(), nullable=False, server_default='paper'))
    op.add_column('orders', sa.Column('decision_id', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('risk_decision_id', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('stop_price', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('take_profit_price', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('time_in_force', sa.String(), nullable=True))
    op.alter_column('orders', 'execution_mode', server_default=None)
    op.create_foreign_key('fk_orders_broker_id', 'orders', 'brokers', ['broker_id'], ['id'])
    op.create_foreign_key('fk_orders_decision_id', 'orders', 'decisions', ['decision_id'], ['id'])
    op.create_foreign_key('fk_orders_risk_decision_id', 'orders', 'risk_decisions', ['risk_decision_id'], ['id'])

    op.drop_constraint('ck_orders_order_type', 'orders', type_='check')
    op.create_check_constraint(
        'ck_orders_order_type', 'orders',
        "order_type IN ('market','limit','stop','stop_limit','take_profit','take_profit_limit')",
    )
    op.drop_constraint('ck_orders_status', 'orders', type_='check')
    op.create_check_constraint(
        'ck_orders_status', 'orders',
        "status IN ('new','submitted','filled','partially_filled','cancelled','rejected',"
        "'cancel_pending','expired','failed','unknown')",
    )
    op.create_check_constraint(
        'ck_orders_execution_mode', 'orders', "execution_mode IN ('paper','sandbox','simulation','live')"
    )
    op.create_check_constraint(
        'ck_orders_time_in_force', 'orders', "time_in_force IS NULL OR time_in_force IN ('day','gtc','ioc','fok')"
    )

    # -- trading_events: new order lifecycle / broker-health event types ---
    op.drop_constraint('ck_trading_events_event_type', 'trading_events', type_='check')
    op.create_check_constraint(
        'ck_trading_events_event_type', 'trading_events',
        "event_type IN ('order_submitted','order_filled','order_rejected',"
        "'position_opened','position_closed','risk_blocked','no_trade',"
        "'trading_paused','trading_resumed','kill_switch_triggered',"
        "'kill_switch_released','reconciliation_mismatch',"
        "'portfolio_emergency_action','loss_streak_detected',"
        "'worker_restarted','crash_loop_protection_triggered',"
        "'order_partially_filled','order_cancelled','broker_health_degraded')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_trading_events_event_type', 'trading_events', type_='check')
    op.create_check_constraint(
        'ck_trading_events_event_type', 'trading_events',
        "event_type IN ('order_submitted','order_filled','order_rejected',"
        "'position_opened','position_closed','risk_blocked','no_trade',"
        "'trading_paused','trading_resumed','kill_switch_triggered',"
        "'kill_switch_released','reconciliation_mismatch',"
        "'portfolio_emergency_action','loss_streak_detected',"
        "'worker_restarted','crash_loop_protection_triggered')",
    )

    op.drop_constraint('ck_orders_time_in_force', 'orders', type_='check')
    op.drop_constraint('ck_orders_execution_mode', 'orders', type_='check')
    op.drop_constraint('ck_orders_status', 'orders', type_='check')
    op.create_check_constraint(
        'ck_orders_status', 'orders',
        "status IN ('new','submitted','filled','partially_filled','cancelled','rejected')",
    )
    op.drop_constraint('ck_orders_order_type', 'orders', type_='check')
    op.create_check_constraint('ck_orders_order_type', 'orders', "order_type IN ('market','limit','stop')")

    op.drop_constraint('fk_orders_risk_decision_id', 'orders', type_='foreignkey')
    op.drop_constraint('fk_orders_decision_id', 'orders', type_='foreignkey')
    op.drop_constraint('fk_orders_broker_id', 'orders', type_='foreignkey')
    op.drop_column('orders', 'time_in_force')
    op.drop_column('orders', 'take_profit_price')
    op.drop_column('orders', 'stop_price')
    op.drop_column('orders', 'risk_decision_id')
    op.drop_column('orders', 'decision_id')
    op.drop_column('orders', 'execution_mode')
    op.drop_column('orders', 'broker_id')

    op.drop_index('ix_reconciliation_runs_ts', table_name='reconciliation_runs')
    op.drop_table('reconciliation_runs')
    op.drop_table('broker_events')
    op.drop_index('ix_executions_order_id', table_name='executions')
    op.drop_table('executions')
    op.drop_index('ix_broker_position_snapshots_ts', table_name='broker_position_snapshots')
    op.drop_table('broker_position_snapshots')
    op.drop_index('ix_account_snapshots_ts', table_name='account_snapshots')
    op.drop_table('account_snapshots')
    op.drop_index('ix_broker_health_checks_ts', table_name='broker_health_checks')
    op.drop_table('broker_health_checks')
    op.drop_table('brokers')

    op.drop_column('assets', 'min_notional')
    op.drop_column('assets', 'min_quantity')
    op.drop_column('assets', 'step_size')
    op.drop_column('assets', 'tick_size')
