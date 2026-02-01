"""alter rule_fingerprint to text

Revision ID: 4ef2c767664c
Revises: 87594ea6d308
Create Date: 2024-08-25 16:40:38.661553

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4ef2c767664c"
down_revision = "87594ea6d308"
branch_labels = None
depends_on = None


def upgrade() -> None:

    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.alter_column(
            "rule_fingerprint",
            existing_type=sa.VARCHAR(),
            type_=sa.TEXT(),
            nullable=True,
            existing_server_default=sa.text("('')"),
        )


def downgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.alter_column(
            "rule_fingerprint",
            existing_type=sa.TEXT(),
            type_=sa.VARCHAR(),
            nullable=False,
            existing_server_default=sa.text("('')"),
        )
