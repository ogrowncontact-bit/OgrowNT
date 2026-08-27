"""prompt14_command_center

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-21 20:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- system_health: numeric score + readiness (§116-119) ---------------
    op.add_column('system_health', sa.Column('health_score', sa.Float(), nullable=True))
    op.add_column('system_health', sa.Column('readiness_state', sa.String(), nullable=True))
    op.create_check_constraint(
        'ck_system_health_readiness_state', 'system_health',
        "readiness_state IS NULL OR readiness_state IN ('ready','caution','degraded','not_ready','halted')",
    )

    # -- incidents (§59-62) --------------------------------------------------
    op.create_table(
        'incidents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='detected'),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_event_type', sa.String(), nullable=True),
        sa.Column('source_entity_type', sa.String(), nullable=True),
        sa.Column('source_entity_id', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "category IN ('system','risk','data','execution','broker','agent')",
            name='ck_incidents_category',
        ),
        sa.CheckConstraint(
            "severity IN ('info','low','medium','high','critical','emergency')",
            name='ck_incidents_severity',
        ),
        sa.CheckConstraint(
            "status IN ('detected','investigating','mitigated','recovering','resolved','closed')",
            name='ck_incidents_status',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('incidents', 'status', server_default=None)
    op.create_index('ix_incidents_detected_at', 'incidents', ['detected_at'])
    op.create_index('ix_incidents_status', 'incidents', ['status'])


def downgrade() -> None:
    op.drop_index('ix_incidents_status', table_name='incidents')
    op.drop_index('ix_incidents_detected_at', table_name='incidents')
    op.drop_table('incidents')

    op.drop_constraint('ck_system_health_readiness_state', 'system_health', type_='check')
    op.drop_column('system_health', 'readiness_state')
    op.drop_column('system_health', 'health_score')
