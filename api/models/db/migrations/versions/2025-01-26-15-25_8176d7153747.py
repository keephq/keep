"""Add manual field in topology-service

Revision ID: 8176d7153747
Revises: 7fde94be79e4
Create Date: 2025-01-26 15:25:23.811890

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8176d7153747"
down_revision = "7fde94be79e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("topologyservice", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_manual", sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    with op.batch_alter_table("topologyservice", schema=None) as batch_op:
        batch_op.drop_column("is_manual")

    # ### end Alembic commands ###
