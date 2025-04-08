"""Workflow Versions

Revision ID: 0b6af21c56a3
Revises: 78777e6b12d3
Create Date: 2025-04-02 16:51:51.974499

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0b6af21c56a3"
down_revision = "78777e6b12d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing foreign key constraint first
    # Get the constraint name (this varies by database)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    for fk in inspector.get_foreign_keys("workflowexecution"):
        if (
            fk["referred_table"] == "workflow"
            and "workflow_id" in fk["constrained_columns"]
        ):
            op.drop_constraint(fk["name"], "workflowexecution", type_="foreignkey")

    # First drop the primary key constraint from the workflow table
    if op.get_bind().dialect.name == "mysql":
        # For MySQL
        op.execute("ALTER TABLE workflow DROP PRIMARY KEY")
    elif op.get_bind().dialect.name == "postgresql":
        # For PostgreSQL
        op.execute("ALTER TABLE workflow DROP CONSTRAINT workflow_pkey")
    elif op.get_bind().dialect.name == "sqlite":
        # For SQLite, you'll need to recreate the table without the primary key
        # This is a bit more complex, consider using batch_alter_table
        with op.batch_alter_table("workflow") as batch_op:
            batch_op.drop_constraint("pk_workflow", type_="primary")

    # First update the workflow table
    with op.batch_alter_table("workflow", schema=None) as batch_op:
        # Add is_latest column
        batch_op.add_column(
            sa.Column(
                "is_latest", sa.Boolean(), nullable=False, server_default=sa.true()
            )
        )
        # Create a non-unique index on id (since we want multiple rows with same id)
        batch_op.create_index("ix_workflow_id", ["id"], unique=False)

        # Create a unique index on (id, revision) for proper versioning
        batch_op.create_index(
            "ix_workflow_id_revision", ["id", "revision"], unique=True
        )

    # Then create a new composite primary key
    with op.batch_alter_table("workflow", schema=None) as batch_op:
        batch_op.create_primary_key("pk_workflow", ["id", "revision"])

    # Then update workflowexecution with new column and new indexes
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "workflow_revision", sa.Integer(), nullable=False, server_default="1"
            )
        )
        # Create new indexes first
        batch_op.create_index(
            "idx_workflowexecution_workflow_revision",
            ["workflow_id", "workflow_revision"],
            unique=False,
        )
        # Create new index with updated columns
        batch_op.create_index(
            "idx_workflowexecution_tenant_workflow_id_rev_timestamp",
            ["tenant_id", "workflow_id", "workflow_revision", "started"],
            unique=False,
        )
        batch_op.create_index(
            "idx_workflowexecution_workflow_rev_tenant_started_status",
            [
                "workflow_id",
                "workflow_revision",
                "tenant_id",
                "started",
                sa.text("status(255)"),
            ],
            unique=False,
        )
        # Create a foreign key that references both id and revision columns
        batch_op.create_foreign_key(
            "fk_workflowexecution_workflow",
            "workflow",
            ["workflow_id", "workflow_revision"],
            ["id", "revision"],
        )

    # Now we can safely drop the old index
    # Use a separate operation to avoid foreign key issues
    op.execute(
        "DROP INDEX idx_workflowexecution_tenant_workflow_id_timestamp ON workflowexecution"
    )
    op.execute(
        "DROP INDEX idx_workflowexecution_workflow_tenant_started_status ON workflowexecution"
    )

    # ### end Alembic commands ###


def downgrade() -> None:
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.drop_constraint("fk_workflowexecution_workflow", type_="foreignkey")
        batch_op.drop_index("idx_workflowexecution_workflow_rev_tenant_started_status")
        batch_op.drop_index("idx_workflowexecution_workflow_revision")
        batch_op.drop_index("idx_workflowexecution_tenant_workflow_id_rev_timestamp")
        batch_op.create_index(
            "idx_workflowexecution_tenant_workflow_id_timestamp",
            ["tenant_id", "workflow_id", "started"],
            unique=False,
        )
        batch_op.drop_column("workflow_revision")

    with op.batch_alter_table("workflow", schema=None) as batch_op:
        batch_op.drop_constraint("pk_workflow", type_="primary")
        batch_op.drop_index("ix_workflow_id_revision")
        batch_op.drop_index("ix_workflow_id")
        batch_op.create_primary_key("pk_workflow", ["id"])
        # Recreate the unique index on id that would be expected
        batch_op.create_index("ix_workflow_id", ["id"], unique=True)
        batch_op.drop_column("is_latest")
