"""AI config

Revision ID: 3f056d747d9e
Revises: ef0b5b0df41c
Create Date: 2024-10-26 17:03:02.383942

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "3f056d747d9e"
down_revision = "ef0b5b0df41c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "externalaiconfigandmetadata",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("algorithm_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("settings", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("feedback_logs", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("externalaiconfigandmetadata")
    # ### end Alembic commands ###
