"""Add idx_alert_tenant_provider index

Revision ID: ea25d9402518
Revises: 35ebba262eb0
Create Date: 2025-02-20 23:15:59.831382

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "ea25d9402518"
down_revision = "35ebba262eb0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alert", schema=None) as batch_op:
        if not op.get_bind().dialect.has_index(
            op.get_bind(), "alert", "idx_alert_tenant_provider"
        ):
            batch_op.create_index(
                "idx_alert_tenant_provider", ["tenant_id", "provider_id"], unique=False
            )


def downgrade() -> None:
    with op.batch_alter_table("alert", schema=None) as batch_op:
        batch_op.drop_index("idx_alert_tenant_provider")
