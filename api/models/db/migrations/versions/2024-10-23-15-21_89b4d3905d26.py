"""Merge Incidents

Revision ID: 89b4d3905d26
Revises: 8438f041ee0e
Create Date: 2024-10-21 20:48:40.151171

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "89b4d3905d26"
down_revision = "8438f041ee0e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "merged_into_incident_id",
                sqlalchemy_utils.types.uuid.UUIDType(binary=False),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("merged_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("merged_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_incident_merged_into_incident_id",
            "incident",
            ["merged_into_incident_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_incident_merged_into_incident_id", type_="foreignkey"
        )
        batch_op.drop_column("merged_by")
        batch_op.drop_column("merged_at")
        batch_op.drop_column("merged_into_incident_id")
