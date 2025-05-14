"""Add threshold field to Rule

Revision ID: fcef2c58b21c
Revises: 7b687c555318
Create Date: 2025-05-15 00:34:31.753003

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "fcef2c58b21c"
down_revision = "7b687c555318"
branch_labels = None
depends_on = None


def upgrade() -> None:

    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.add_column(sa.Column("threshold", sa.Integer(), nullable=False, server_default="1"))
        batch_op.create_check_constraint("rule_threshold_positive_int_constraint", "threshold>0")


def downgrade() -> None:

    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.drop_constraint("rule_threshold_positive_int_constraint",  type_="check")
        batch_op.drop_column("threshold")
