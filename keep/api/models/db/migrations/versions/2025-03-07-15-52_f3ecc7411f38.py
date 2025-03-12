"""Add is_candidate and is_visible flags to Incident to replace is_confirmed

Revision ID: f3ecc7411f38
Revises: 0b80bda47ee2
Create Date: 2025-03-07 15:52:10.729973

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f3ecc7411f38"
down_revision = "0b80bda47ee2"
branch_labels = None
depends_on = None



def upgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_candidate", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("is_visible", sa.Boolean(), server_default=sa.true(), nullable=False))

    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.execute("""UPDATE incident SET is_candidate = not is_confirmed""")
        batch_op.drop_column("is_confirmed")

def downgrade() -> None:

    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_confirmed",
                sa.BOOLEAN(),
                server_default=sa.false(),
                nullable=False,
            )
        )

    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.execute("""UPDATE incident SET is_confirmed = not is_candidate""")
        batch_op.drop_column("is_visible")
        batch_op.drop_column("is_candidate")
