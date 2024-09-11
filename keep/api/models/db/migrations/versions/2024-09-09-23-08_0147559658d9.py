"""Add status to Incident model

Revision ID: 0147559658d9
Revises: 1aacee84447e
Create Date: 2024-09-09 23:08:16.410243

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0147559658d9"
down_revision = "1aacee84447e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False,
                      default="firing", server_default="firing")
        )
        batch_op.create_index(
            batch_op.f("ix_incident_status"), ["status"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_incident_status"))
        batch_op.drop_column("status")