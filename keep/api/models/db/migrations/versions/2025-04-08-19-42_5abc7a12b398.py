"""Add provider pulling_interval column

Revision ID: 5abc7a12b398
Revises: 59991b568c7d
Create Date: 2025-04-08 19:42:34.421933

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5abc7a12b398"
down_revision = "59991b568c7d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("provider", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pulling_interval", sa.Integer(), nullable=True))


def downgrade() -> None:

    with op.batch_alter_table("provider", schema=None) as batch_op:
        batch_op.drop_column("pulling_interval")
