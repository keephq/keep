"""Add resolve_on action to Rule

Revision ID: 017d759805d9
Revises: 01ebe17218c0
Create Date: 2024-10-05 18:37:45.152090

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "017d759805d9"
down_revision = "01ebe17218c0"
branch_labels = None
depends_on = None


def upgrade() -> None:

    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("resolve_on", sqlmodel.sql.sqltypes.AutoString(), nullable=False,
                      default="never", server_default="never")
        )


def downgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.drop_column("resolve_on")