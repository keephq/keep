"""add WorkflowToIncidentExecution

Revision ID: 3ccad45f29ec
Revises: 1c650a429672
Create Date: 2024-09-01 13:08:17.141139

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "3ccad45f29ec"
down_revision = "1c650a429672"
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
