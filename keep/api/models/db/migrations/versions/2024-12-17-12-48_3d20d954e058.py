"""Add index to WorkflowExecution

Revision ID: 3d20d954e058
Revises: 55cc64020f6d
Create Date: 2024-12-17 12:48:04.713649

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3d20d954e058"
down_revision = "55cc64020f6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.create_index(
            "idx_workflowexecution_tenant_workflow_id_timestamp",
            ["tenant_id", "workflow_id", sa.desc("started")],
            unique=False,
        )
        if op.get_bind().dialect.name == "mysql":
            batch_op.create_index(
                "idx_workflowexecution_workflow_tenant_started_status",
                [
                    "workflow_id",
                    "tenant_id",
                    sa.desc("started"),
                    sa.text("status(255)"),
                ],
                unique=False,
            )
        else:
            batch_op.create_index(
                "idx_workflowexecution_workflow_tenant_started_status",
                ["workflow_id", "tenant_id", sa.desc("started"), "status"],
                unique=False,
            )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.drop_index("idx_workflowexecution_workflow_tenant_started_status")
        batch_op.drop_index("idx_workflowexecution_tenant_workflow_id_timestamp")
    # ### end Alembic commands ###
