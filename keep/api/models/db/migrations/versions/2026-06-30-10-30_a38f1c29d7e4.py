"""feat: add incident enrichments to correlation rules

Revision ID: a38f1c29d7e4
Revises: 67ff7efffed4
Create Date: 2026-06-30 10:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a38f1c29d7e4"
down_revision = "67ff7efffed4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("incident_enrichments", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("rule", schema=None) as batch_op:
        batch_op.drop_column("incident_enrichments")
