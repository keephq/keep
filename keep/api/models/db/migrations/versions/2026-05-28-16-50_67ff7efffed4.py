"""feat: add is_provisioned and provisioned_file to MappingRule

Revision ID: 67ff7efffed4
Revises: 9dd1be4539e0
Create Date: 2026-05-28 16:50:00.000000

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "67ff7efffed4"
down_revision = "9dd1be4539e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mappingrule", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_provisioned",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "provisioned_file",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("mappingrule", schema=None) as batch_op:
        batch_op.drop_column("provisioned_file")
        batch_op.drop_column("is_provisioned")
