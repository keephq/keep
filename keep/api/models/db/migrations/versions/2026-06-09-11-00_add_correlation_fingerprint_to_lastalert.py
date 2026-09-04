"""feat: add correlation_fingerprint to LastAlert

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-09 11:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a1"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("lastalert") as batch_op:
        batch_op.add_column(
            sa.Column("correlation_fingerprint", sa.String(), nullable=True)
        )
        batch_op.create_index(
            "idx_lastalert_tenant_correlation_fingerprint",
            ["tenant_id", "correlation_fingerprint"],
        )


def downgrade() -> None:
    with op.batch_alter_table("lastalert") as batch_op:
        batch_op.drop_index("idx_lastalert_tenant_correlation_fingerprint")
        batch_op.drop_column("correlation_fingerprint")
