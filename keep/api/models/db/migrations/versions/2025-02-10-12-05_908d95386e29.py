"""Add incident severity_forced flag

Revision ID: 908d95386e29
Revises: e343054ae740
Create Date: 2025-02-05 12:05:19.795904

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "908d95386e29"
down_revision = "e343054ae740"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.add_column(sa.Column("forced_severity", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:

    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.drop_column("forced_severity")
