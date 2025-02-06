"""Add manual field in topology-service

Revision ID: 8176d7153747
Revises: d359baaf0836
Create Date: 2025-01-26 15:25:23.811890

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "8176d7153747"
down_revision = "d359baaf0836"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("topologyservice", schema=None) as batch_op:
        batch_op.add_column(sa.Column("manual", sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    with op.batch_alter_table("topologyservice", schema=None) as batch_op:
        batch_op.drop_column("manual")

    # ### end Alembic commands ###
