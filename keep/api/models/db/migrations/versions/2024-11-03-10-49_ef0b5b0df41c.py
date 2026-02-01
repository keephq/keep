"""Adding new index on alert hash

Revision ID: ef0b5b0df41c
Revises: 273b29f368b7
Create Date: 2024-11-03 10:49:04.708264

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "ef0b5b0df41c"
down_revision = "273b29f368b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Using batch operation to ensure compatibility with multiple databases
    with op.batch_alter_table("alert", schema=None) as batch_op:
        batch_op.create_index(
            "ix_alert_tenant_fingerprint_timestamp",
            ["tenant_id", "fingerprint", "timestamp"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("alert", schema=None) as batch_op:
        batch_op.drop_index("ix_alert_tenant_fingerprint_timestamp")
