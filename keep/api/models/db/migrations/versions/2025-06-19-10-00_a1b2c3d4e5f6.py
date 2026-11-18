"""fix: Change secret.value from VARCHAR to TEXT

Revision ID: a1b2c3d4e5f6
Revises: 9dd1be4539e0
Create Date: 2025-06-19 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9dd1be4539e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("secret") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.String(length=255),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("secret") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.Text(),
            type_=sa.String(length=255),
            existing_nullable=False,
        )
