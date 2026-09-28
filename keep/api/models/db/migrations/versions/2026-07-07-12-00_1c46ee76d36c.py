"""feat: add max_incident_window to Rule

Revision ID: 1c46ee76d36c
Revises: 67ff7efffed4
Create Date: 2026-07-07 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1c46ee76d36c"
down_revision = "67ff7efffed4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("max_incident_window", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.drop_column("max_incident_window")
