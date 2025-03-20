"""Default workflow_id=None for WorkflowExecution for test runs

Revision ID: 971abbbf0a2c
Revises: c0880e315ebe
Create Date: 2025-03-18 14:54:56.003392

"""

from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "971abbbf0a2c"
down_revision = "c0880e315ebe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.alter_column(
            "workflow_id", existing_type=mysql.VARCHAR(length=255), nullable=True
        )


def downgrade() -> None:
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        # Update NULL values to a default value first
        op.execute("UPDATE workflowexecution SET workflow_id = 'legacy_null' WHERE workflow_id IS NULL")
        batch_op.alter_column(
            "workflow_id", existing_type=mysql.VARCHAR(length=255), nullable=False
        )