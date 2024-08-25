"""Modify summary column types

Revision ID: 1c650a429672
Revises: 87594ea6d308
Create Date: 2024-08-25 16:08:06.271696

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "1c650a429672"
down_revision = "87594ea6d308"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.alter_column(
            "user_summary",
            existing_type=sa.VARCHAR(),
            type_=sa.TEXT(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "generated_summary",
            existing_type=sa.VARCHAR(),
            type_=sa.TEXT(),
            existing_nullable=True,
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.alter_column(
            "generated_summary",
            existing_type=sa.TEXT(),
            type_=sa.VARCHAR(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "user_summary",
            existing_type=sa.TEXT(),
            type_=sa.VARCHAR(),
            existing_nullable=True,
        )
    # ### end Alembic commands ###
