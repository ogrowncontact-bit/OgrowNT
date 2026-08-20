"""prompt9_multi_agent

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-20 12:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('agents',
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('directional', sa.Boolean(), nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('quarantined_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('quarantine_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('active','quarantined','disabled')", name='ck_agents_status'),
    sa.PrimaryKeyConstraint('code')
    )

    op.create_table('decisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('decision_state', sa.String(), nullable=False),
    sa.Column('consensus_score', sa.Float(), nullable=False),
    sa.Column('contradiction_score', sa.Float(), nullable=False),
    sa.Column('reasoning_summary', sa.Text(), nullable=False),
    sa.Column('agent_inputs', sa.JSON(), nullable=False),
    sa.Column('blocked_reason', sa.String(), nullable=True),
    sa.Column('critical_agent_failure', sa.Boolean(), nullable=False),
    sa.CheckConstraint(
        "decision_state IN ('strong_long_bias','long_bias','neutral','short_bias',"
        "'strong_short_bias','no_trade','blocked')",
        name='ck_decisions_decision_state',
    ),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decisions_ts', 'decisions', ['ts'])
    op.create_index('ix_decisions_asset_id', 'decisions', ['asset_id'])

    op.create_table('agent_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('agent_code', sa.String(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('decision_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('signal', sa.String(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('risk_flags', sa.JSON(), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=True),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('ok','unavailable','quarantined')", name='ck_agent_messages_status'),
    sa.CheckConstraint(
        "signal IN ('strong_long','long','neutral','short','strong_short','no_read')",
        name='ck_agent_messages_signal',
    ),
    sa.ForeignKeyConstraint(['agent_code'], ['agents.code']),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
    sa.ForeignKeyConstraint(['decision_id'], ['decisions.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_messages_agent_code', 'agent_messages', ['agent_code'])
    op.create_index('ix_agent_messages_decision_id', 'agent_messages', ['decision_id'])

    op.create_table('agent_predictions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('agent_code', sa.String(), nullable=False),
    sa.Column('agent_message_id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=False),
    sa.Column('predicted_direction', sa.String(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('reference_price', sa.Float(), nullable=False),
    sa.Column('predicted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('evaluate_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('outcome', sa.String(), nullable=False),
    sa.Column('outcome_price', sa.Float(), nullable=True),
    sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("outcome IN ('pending','correct','incorrect')", name='ck_agent_predictions_outcome'),
    sa.ForeignKeyConstraint(['agent_code'], ['agents.code']),
    sa.ForeignKeyConstraint(['agent_message_id'], ['agent_messages.id']),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_predictions_agent_code', 'agent_predictions', ['agent_code'])
    op.create_index('ix_agent_predictions_outcome', 'agent_predictions', ['outcome'])
    op.create_index('ix_agent_predictions_evaluate_at', 'agent_predictions', ['evaluate_at'])

    op.create_table('agent_reliability',
    sa.Column('agent_code', sa.String(), nullable=False),
    sa.Column('as_of', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sample_size', sa.Integer(), nullable=False),
    sa.Column('correct_count', sa.Integer(), nullable=False),
    sa.Column('accuracy', sa.Float(), nullable=True),
    sa.Column('avg_confidence_when_correct', sa.Float(), nullable=True),
    sa.Column('avg_confidence_when_incorrect', sa.Float(), nullable=True),
    sa.Column('overconfidence_gap', sa.Float(), nullable=True),
    sa.Column('reliability_score', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['agent_code'], ['agents.code']),
    sa.PrimaryKeyConstraint('agent_code', 'as_of')
    )

    op.create_table('agent_health',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('agent_code', sa.String(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('latency_ms', sa.Float(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['agent_code'], ['agents.code']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_health_agent_code', 'agent_health', ['agent_code'])
    op.create_index('ix_agent_health_ts', 'agent_health', ['ts'])

    op.create_table('contradictions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('decision_id', sa.Integer(), nullable=False),
    sa.Column('agent_code_a', sa.String(), nullable=False),
    sa.Column('agent_code_b', sa.String(), nullable=False),
    sa.Column('signal_a', sa.String(), nullable=False),
    sa.Column('signal_b', sa.String(), nullable=False),
    sa.Column('severity', sa.Float(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['decision_id'], ['decisions.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_contradictions_decision_id', 'contradictions', ['decision_id'])

    op.add_column('learned_rules', sa.Column('proposed_by_agent', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('learned_rules', 'proposed_by_agent')
    op.drop_index('ix_contradictions_decision_id', table_name='contradictions')
    op.drop_table('contradictions')
    op.drop_index('ix_agent_health_ts', table_name='agent_health')
    op.drop_index('ix_agent_health_agent_code', table_name='agent_health')
    op.drop_table('agent_health')
    op.drop_table('agent_reliability')
    op.drop_index('ix_agent_predictions_evaluate_at', table_name='agent_predictions')
    op.drop_index('ix_agent_predictions_outcome', table_name='agent_predictions')
    op.drop_index('ix_agent_predictions_agent_code', table_name='agent_predictions')
    op.drop_table('agent_predictions')
    op.drop_index('ix_agent_messages_decision_id', table_name='agent_messages')
    op.drop_index('ix_agent_messages_agent_code', table_name='agent_messages')
    op.drop_table('agent_messages')
    op.drop_index('ix_decisions_asset_id', table_name='decisions')
    op.drop_index('ix_decisions_ts', table_name='decisions')
    op.drop_table('decisions')
    op.drop_table('agents')
