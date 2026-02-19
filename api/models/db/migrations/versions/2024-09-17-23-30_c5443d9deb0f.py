"""Add status to Incident model

Revision ID: c5443d9deb0f
Revises: 710b4ff1d19e
Create Date: 2024-09-11 23:30:04.308017

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "c5443d9deb0f"
down_revision = "938b1aa62d5c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, default="firing",
                      server_default="firing")
        )
        batch_op.create_index(
            batch_op.f("ix_incident_status"), ["status"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_incident_status"))
        batch_op.drop_column("status")
