"""Add Rule.create_on

Revision ID: 7297ae99cd21
Revises: 3d20d954e058
Create Date: 2024-12-10 19:11:28.512095

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "7297ae99cd21"
down_revision = "3d20d954e058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("create_on", sqlmodel.sql.sqltypes.AutoString(), nullable=False, default="any", server_default="any")
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.drop_column("create_on")
