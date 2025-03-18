"""multi-level mapping

Revision ID: aff0128aa8f1
Revises: f3ecc7411f38
Create Date: 2025-03-16 11:08:09.846457

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "aff0128aa8f1"
down_revision = "f3ecc7411f38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("mappingrule", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_multi_level", sa.Boolean(), nullable=False))
        batch_op.add_column(
            sa.Column(
                "new_property_name",
                sqlmodel.sql.sqltypes.AutoString(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "prefix_to_remove",
                sqlmodel.sql.sqltypes.AutoString(length=255),
                nullable=True,
            )
        )

    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "multi_level",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("(FALSE)"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "multi_level_property_name",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=True,
            )
        )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("mappingrule", schema=None) as batch_op:
        batch_op.drop_column("prefix_to_remove")
        batch_op.drop_column("new_property_name")
        batch_op.drop_column("is_multi_level")

    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.drop_column("multi_level_property_name")
        batch_op.drop_column("multi_level")
    # ### end Alembic commands ###
