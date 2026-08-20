"""prompt10_research_lab

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-20 14:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('research_hypotheses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('problem', sa.Text(), nullable=False),
    sa.Column('observation', sa.Text(), nullable=False),
    sa.Column('hypothesis', sa.Text(), nullable=False),
    sa.Column('expected_effect', sa.Text(), nullable=False),
    sa.Column('risk', sa.String(), nullable=False),
    sa.Column('assets', sa.JSON(), nullable=False),
    sa.Column('timeframes', sa.JSON(), nullable=False),
    sa.Column('regimes', sa.JSON(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('quality', sa.JSON(), nullable=False),
    sa.Column('priority_score', sa.Float(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
        "status IN ('proposed','approved','rejected','request_more_tests','experimenting','completed')",
        name='ck_research_hypotheses_status',
    ),
    sa.CheckConstraint("risk IN ('low','medium','high')", name='ck_research_hypotheses_risk'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_research_hypotheses_status', 'research_hypotheses', ['status'])

    op.create_table('strategy_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('strategy_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.Column('parent_version_id', sa.Integer(), nullable=True),
    sa.Column('changes', sa.JSON(), nullable=False),
    sa.Column('dsl_definition', sa.JSON(), nullable=True),
    sa.Column('params', sa.JSON(), nullable=False),
    sa.Column('performance', sa.JSON(), nullable=False),
    sa.Column('validation_status', sa.String(), nullable=False),
    sa.Column('lifecycle_status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.String(), nullable=False),
    sa.CheckConstraint(
        "lifecycle_status IN ('experimental','challenger','champion','production_candidate','rolled_back','retired')",
        name='ck_strategy_versions_lifecycle_status',
    ),
    sa.CheckConstraint(
        "validation_status IN ('EXPERIMENTAL','PROMISING','VALIDATING','ROBUST','DEGRADED','REJECTED','QUARANTINED')",
        name='ck_strategy_versions_validation_status',
    ),
    sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id']),
    sa.ForeignKeyConstraint(['parent_version_id'], ['strategy_versions.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('strategy_id', 'version', name='uq_strategy_versions_strategy_id_version'),
    )
    op.create_index('ix_strategy_versions_strategy_id', 'strategy_versions', ['strategy_id'])
    op.create_index('ix_strategy_versions_lifecycle_status', 'strategy_versions', ['lifecycle_status'])

    op.create_table('experiments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('hypothesis_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('control', sa.JSON(), nullable=False),
    sa.Column('candidate', sa.JSON(), nullable=False),
    sa.Column('dataset', sa.JSON(), nullable=False),
    sa.Column('parameters', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=False),
    sa.Column('reproducibility', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "type IN ('backtest','walk_forward','optimization','feature_test','strategy_test',"
        "'regime_test','event_test','genetic_search','ablation')",
        name='ck_experiments_type',
    ),
    sa.CheckConstraint(
        "status IN ('queued','running','completed','failed','rejected','promising',"
        "'validating','approved','quarantined')",
        name='ck_experiments_status',
    ),
    sa.ForeignKeyConstraint(['hypothesis_id'], ['research_hypotheses.id']),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_experiments_hypothesis_id', 'experiments', ['hypothesis_id'])
    op.create_index('ix_experiments_status', 'experiments', ['status'])

    op.create_table('research_approvals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entity_type', sa.String(), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('reviewer', sa.String(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("entity_type IN ('hypothesis','strategy_version','experiment')", name='ck_research_approvals_entity_type'),
    sa.CheckConstraint(
        "action IN ('approve','reject','request_more_tests','promote','rollback','quarantine')",
        name='ck_research_approvals_action',
    ),
    sa.CheckConstraint(
        "status IN ('pending_review','approved','rejected','request_more_tests')",
        name='ck_research_approvals_status',
    ),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_research_approvals_entity', 'research_approvals', ['entity_type', 'entity_id'])

    op.create_table('drift_detections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('drift_type', sa.String(), nullable=False),
    sa.Column('entity', sa.String(), nullable=False),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.Column('severity', sa.String(), nullable=False),
    sa.CheckConstraint("drift_type IN ('feature','market','strategy','agent','data')", name='ck_drift_detections_drift_type'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_drift_detections_ts', 'drift_detections', ['ts'])

    op.create_table('research_queue',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('queue_type', sa.String(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "queue_type IN ('hypothesis','experiment','feature_test','strategy_test',"
        "'regime_test','event_test','knowledge_update')",
        name='ck_research_queue_queue_type',
    ),
    sa.CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name='ck_research_queue_status'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_research_queue_status', 'research_queue', ['status'])

    op.create_table('research_budget_usage',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('resource_type', sa.String(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('experiment_id', sa.Integer(), nullable=True),
    sa.CheckConstraint("resource_type IN ('experiment','backtest','llm_call','api_call')", name='ck_research_budget_usage_resource_type'),
    sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id']),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_research_budget_usage_ts', 'research_budget_usage', ['ts'])

    op.create_table('research_knowledge_edges',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('subject', sa.String(), nullable=False),
    sa.Column('relation', sa.String(), nullable=False),
    sa.Column('object', sa.String(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('sample_size', sa.Integer(), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('source_experiment_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['source_experiment_id'], ['experiments.id']),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_research_knowledge_edges_subject', 'research_knowledge_edges', ['subject'])


def downgrade() -> None:
    op.drop_index('ix_research_knowledge_edges_subject', table_name='research_knowledge_edges')
    op.drop_table('research_knowledge_edges')
    op.drop_index('ix_research_budget_usage_ts', table_name='research_budget_usage')
    op.drop_table('research_budget_usage')
    op.drop_index('ix_research_queue_status', table_name='research_queue')
    op.drop_table('research_queue')
    op.drop_index('ix_drift_detections_ts', table_name='drift_detections')
    op.drop_table('drift_detections')
    op.drop_index('ix_research_approvals_entity', table_name='research_approvals')
    op.drop_table('research_approvals')
    op.drop_index('ix_experiments_status', table_name='experiments')
    op.drop_index('ix_experiments_hypothesis_id', table_name='experiments')
    op.drop_table('experiments')
    op.drop_index('ix_strategy_versions_lifecycle_status', table_name='strategy_versions')
    op.drop_index('ix_strategy_versions_strategy_id', table_name='strategy_versions')
    op.drop_table('strategy_versions')
    op.drop_index('ix_research_hypotheses_status', table_name='research_hypotheses')
    op.drop_table('research_hypotheses')
