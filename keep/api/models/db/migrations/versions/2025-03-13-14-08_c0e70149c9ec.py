"""Unique api key reference

Revision ID: c0e70149c9ec
Revises: ca74b4a04371
Create Date: 2025-03-13 14:08:22.939513

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c0e70149c9ec"
down_revision = "ca74b4a04371"
branch_labels = None
depends_on = None


def upgrade() -> None:

    with op.batch_alter_table("tenantapikey", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "unique_tenant_reference", ["tenant_id", "reference_id"]
        )


def downgrade() -> None:

    with op.batch_alter_table("tenantapikey", schema=None) as batch_op:
        batch_op.drop_constraint("unique_tenant_reference", type_="unique")
