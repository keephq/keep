"""feat: add is_provisioned to Rule

Revision ID: b3f1c9a24d70
Revises: 67ff7efffed4
Create Date: 2026-07-12 09:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b3f1c9a24d70"
down_revision = "67ff7efffed4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_provisioned",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.drop_column("is_provisioned")
