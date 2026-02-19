"""Store timeunit for Rule for better UX

Revision ID: 1aacee84447e
Revises: 1c650a429672
Create Date: 2024-08-26 17:01:21.263004

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "1aacee84447e"
down_revision = "e6653be70b62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("timeunit", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="seconds")
        )


def downgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.drop_column("timeunit")
