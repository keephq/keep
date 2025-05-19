"""Add ignore_statuses to MaintenanceWindowRule

Revision ID: aa167915c4d6
Revises: bedb5f07417b
Create Date: 2025-05-16 14:33:29.828572

"""

import sqlalchemy as sa
from alembic import op
from sqlmodel import Session

from keep.api.models.db.maintenance_window import DEFAULT_ALERT_STATUSES_TO_IGNORE

# revision identifiers, used by Alembic.
revision = "aa167915c4d6"
down_revision = "bedb5f07417b"
branch_labels = None
depends_on = None

migration_metadata = sa.MetaData()

mwr_table = sa.Table(
    'maintenancewindowrule',
    migration_metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('ignore_statuses', sa.JSON)
)

def populate_db():
    session = Session(op.get_bind())
    session.execute(sa.update(mwr_table).values(ignore_statuses=DEFAULT_ALERT_STATUSES_TO_IGNORE))


def upgrade() -> None:

    with op.batch_alter_table("maintenancewindowrule", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ignore_statuses", sa.JSON(), nullable=True))

    populate_db()


def downgrade() -> None:

    with op.batch_alter_table("maintenancewindowrule", schema=None) as batch_op:
        batch_op.drop_column("ignore_statuses")
