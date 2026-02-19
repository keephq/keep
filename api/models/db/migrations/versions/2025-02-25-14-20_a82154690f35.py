"""TopologyApplication repository default_value

Revision ID: a82154690f35
Revises: ea25d9402518
Create Date: 2025-02-25 14:20:04.175052

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "a82154690f35"
down_revision = "ea25d9402518"
branch_labels = None
depends_on = None

def prepare_data():
    session = Session(op.get_bind())

    session.execute(text("UPDATE topologyapplication set description = '' where description is null"))
    session.execute(text("UPDATE topologyapplication set repository = '' where repository is null"))


def upgrade() -> None:
    prepare_data()

    with op.batch_alter_table("topologyapplication", schema=None) as batch_op:
        batch_op.alter_column("description", existing_type=sa.VARCHAR(255), nullable=False)
        batch_op.alter_column("repository", existing_type=sa.VARCHAR(255), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("topologyapplication", schema=None) as batch_op:
        batch_op.alter_column("repository", existing_type=sa.VARCHAR(255), nullable=True)
        batch_op.alter_column("description", existing_type=sa.VARCHAR(255), nullable=True)
