"""Add incident severity_forced flag

Revision ID: 908d95386e29
Revises: d359baaf0836
Create Date: 2025-02-03 20:19:19.795904

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "908d95386e29"
down_revision = "d359baaf0836"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.add_column(sa.Column("forced_severity", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:

    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.drop_column("forced_severity")
