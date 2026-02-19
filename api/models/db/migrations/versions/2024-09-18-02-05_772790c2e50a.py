"""add WorkflowToIncidentExecution

Revision ID: 772790c2e50a
Revises: 49e7c02579db
Create Date: 2024-09-08 02:05:42.739163

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "772790c2e50a"
down_revision = "c5443d9deb0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflowtoincidentexecution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "workflow_execution_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("incident_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_execution_id"],
            ["workflowexecution.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_execution_id", "incident_id"),
    )


def downgrade() -> None:
    op.drop_table("workflowtoincidentexecution")
