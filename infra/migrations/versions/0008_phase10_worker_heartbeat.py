"""phase10 supervisor: worker_last_heartbeat column

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-18 11:27:09.615056

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('system_state', sa.Column('worker_last_heartbeat', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('system_state', 'worker_last_heartbeat')
