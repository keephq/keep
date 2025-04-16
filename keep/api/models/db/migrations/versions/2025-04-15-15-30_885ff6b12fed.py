"""Workflow Versions

Revision ID: 885ff6b12fed
Revises: 59991b568c7d
Create Date: 2025-04-15 15:30:48.099088

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "885ff6b12fed"
down_revision = "59991b568c7d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    connection = op.get_bind()
    dialect = connection.dialect.name
    op.create_table(
        "workflowversion",
        sa.Column("workflow_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("workflow_raw", sa.TEXT(), nullable=True),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("comment", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow.id"],
        ),
        sa.PrimaryKeyConstraint("workflow_id", "revision"),
        sa.UniqueConstraint(
            "workflow_id", "is_current", name="uq_workflow_current_version"
        ),
    )
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "workflow_revision", sa.Integer(), nullable=False, server_default="1"
            )
        )
        batch_op.drop_index("idx_workflowexecution_tenant_workflow_id_timestamp")
        batch_op.create_index(
            "idx_workflowexecution_tenant_workflow_id_timestamp",
            ["tenant_id", "workflow_id", "workflow_revision", "started"],
            unique=False,
        )
        batch_op.drop_index(
            "idx_workflowexecution_workflow_tenant_started_status",
            mysql_length={"status": 255},
        )
        batch_op.create_index(
            "idx_workflowexecution_workflow_tenant_started_status",
            [
                "workflow_id",
                "workflow_revision",
                "tenant_id",
                "started",
                sa.text("status(255)") if dialect == "mysql" else "status",
            ],
            unique=False,
        )
        batch_op.create_index(
            "idx_workflowexecution_workflow_revision",
            ["workflow_id", "workflow_revision"],
            unique=False,
        )
        batch_op.drop_constraint("workflowexecution_ibfk_2", type_="foreignkey")
        batch_op.create_foreign_key(
            None,
            "workflow",
            ["workflow_id"],
            ["id"],
            ondelete="SET DEFAULT",
        )

    # Update existing records with their corresponding workflow revision
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE workflowexecution SET workflow_revision = "
            "(SELECT revision FROM workflow WHERE workflow.id = workflowexecution.workflow_id)"
        )
    )

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(
            "workflowexecution_ibfk_2",
            "workflow",
            ["workflow_id"],
            ["id"],
            ondelete="SET DEFAULT",
        )
        batch_op.drop_index("idx_workflowexecution_workflow_revision")
        batch_op.drop_index("idx_workflowexecution_workflow_tenant_started_status")
        batch_op.create_index(
            "idx_workflowexecution_workflow_tenant_started_status",
            ["workflow_id", "tenant_id", "started", "status"],
            unique=False,
            mysql_length={"status": 255},
        )
        batch_op.drop_index("idx_workflowexecution_tenant_workflow_id_timestamp")
        batch_op.create_index(
            "idx_workflowexecution_tenant_workflow_id_timestamp",
            ["tenant_id", "workflow_id", "started"],
            unique=False,
        )
        batch_op.drop_column("workflow_revision")

    op.drop_table("workflowversion")
    # ### end Alembic commands ###
