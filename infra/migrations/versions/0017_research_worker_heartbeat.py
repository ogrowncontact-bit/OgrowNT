"""research_worker_heartbeat

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-20 15:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('system_state', sa.Column('research_worker_last_heartbeat', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('system_state', 'research_worker_last_heartbeat')
