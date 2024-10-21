"""Merge Incidents

Revision ID: 89b4d3905d26
Revises: 83c1020be97d
Create Date: 2024-10-21 20:48:40.151171

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op
from sqlalchemy.dialects import mysql, postgresql

# revision identifiers, used by Alembic.
revision = "89b4d3905d26"
down_revision = "83c1020be97d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "merged_into_id",
                sqlalchemy_utils.types.uuid.UUIDType(binary=False),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("merged_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("merged_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.create_foreign_key(
            None, "incident", ["merged_into_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.drop_column("merged_by")
        batch_op.drop_column("merged_at")
        batch_op.drop_column("merged_into_id")
