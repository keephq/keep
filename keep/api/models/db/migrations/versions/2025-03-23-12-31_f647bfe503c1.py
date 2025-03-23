"""Default workflow_id=test for test runs

Revision ID: f647bfe503c1
Revises: 971abbbf0a2c
Create Date: 2025-03-23 12:31:13.340022

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql   

# revision identifiers, used by Alembic.
revision = "f647bfe503c1"
down_revision = "971abbbf0a2c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # First update all NULL workflow_id values to 'test'
    op.execute("UPDATE workflowexecution SET workflow_id = 'test' WHERE workflow_id IS NULL")
    
    # Then make the column NOT NULL with DEFAULT 'test'
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.alter_column(
            "workflow_id", 
            existing_type=mysql.VARCHAR(length=255), 
            nullable=False,
            server_default="TEST"  # Add this to set default value
        )
        batch_op.drop_index("idx_status_started", mysql_length={"status": 255})
        batch_op.drop_index(
            "idx_workflowexecution_workflow_tenant_started_status",
            mysql_length={"status": 255},
        )
        batch_op.create_index(
            "idx_workflowexecution_workflow_tenant_started_status",
            ["workflow_id", "tenant_id", "started", sa.text("status(255)")],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.drop_index("idx_workflowexecution_workflow_tenant_started_status")
        batch_op.create_index(
            "idx_workflowexecution_workflow_tenant_started_status",
            ["workflow_id", "tenant_id", "started", "status"],
            unique=False,
            mysql_length={"status": 255},
        )
        batch_op.create_index(
            "idx_status_started",
            ["status", "started"],
            unique=False,
            mysql_length={"status": 255},
        )
        # Remove server_default in downgrade
        batch_op.alter_column(
            "workflow_id", 
            existing_type=mysql.VARCHAR(length=255), 
            nullable=True,
            server_default=None
        )
        
    # Convert 'test' values back to NULL in downgrade
    op.execute("UPDATE workflowexecution SET workflow_id = NULL WHERE workflow_id = 'test'")