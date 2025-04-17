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
    )

    # Then handle column and index changes
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "workflow_revision", sa.Integer(), nullable=False, server_default="1"
            )
        )
        batch_op.create_index(
            "idx_workflowexecution_tenant_workflow_id_revision_timestamp",
            ["tenant_id", "workflow_id", "workflow_revision", "started"],
            unique=False,
        )
        batch_op.create_index(
            "idx_workflowexecution_workflow_revision_tenant_started_status",
            [
                "workflow_id",
                "workflow_revision",
                "tenant_id",
                "started",
                "status",
            ],
            mysql_length={"status": 255},
            unique=False,
        )
        batch_op.create_index(
            "idx_workflowexecution_workflow_revision",
            ["workflow_id", "workflow_revision"],
            unique=False,
        )

    # Update existing records with their corresponding workflow revision
    connection = op.get_bind()

    # Remove orphaned workflow executions
    connection.execute(
        sa.text(
            """
            DELETE FROM workflowexecution WHERE workflow_id NOT IN (SELECT id FROM workflow)
            """
        )
    )

    # Update workflow executions with their corresponding workflow revision, skipping null revisions
    connection.execute(
        sa.text(
            """
            UPDATE workflowexecution 
            SET workflow_revision = (
                SELECT revision 
                FROM workflow 
                WHERE workflow.id = workflowexecution.workflow_id
                AND workflow.revision IS NOT NULL
            )
            WHERE EXISTS (
                SELECT 1 
                FROM workflow 
                WHERE workflow.id = workflowexecution.workflow_id
                AND workflow.revision IS NOT NULL
            )
            """
        )
    )

    # Create initial workflow versions for existing workflows
    connection.execute(
        sa.text(
            """
            INSERT INTO workflowversion (
                workflow_id, 
                revision, 
                workflow_raw, 
                updated_by, 
                updated_at, 
                is_valid, 
                is_current,
                comment
            )
            SELECT 
                id as workflow_id,
                COALESCE(revision, 1) as revision,
                workflow_raw,
                COALESCE(updated_by, created_by) as updated_by,
                COALESCE(last_updated, CURRENT_DATE) as updated_at,
                true as is_valid,
                true as is_current,
                'Initial version migration' as comment
            FROM workflow
            """
        )
    )

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    # First drop foreign key constraints because they prevent dropping indexes (at least in mysql)
    inspector = sa.inspect(op.get_bind())
    foreign_keys = inspector.get_foreign_keys("workflowexecution")
    for foreign_key in foreign_keys:
        if foreign_key["name"]:
            op.drop_constraint(
                foreign_key["name"], "workflowexecution", type_="foreignkey"
            )
        else:
            print(f"foreign_key {foreign_key} has no name, skipping")

    # Then handle column and index changes
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.drop_index("idx_workflowexecution_workflow_revision")
        batch_op.drop_index(
            "idx_workflowexecution_tenant_workflow_id_revision_timestamp"
        )
        batch_op.drop_index(
            "idx_workflowexecution_workflow_revision_tenant_started_status"
        )
        batch_op.drop_column("workflow_revision")

    # Finally recreate foreign key constraints
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "workflowexecution_ibfk_1",
            "tenant",
            ["tenant_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "workflowexecution_ibfk_2",
            "workflow",
            ["workflow_id"],
            ["id"],
            ondelete="SET DEFAULT",
        )

    op.drop_table("workflowversion")
    # ### end Alembic commands ###
