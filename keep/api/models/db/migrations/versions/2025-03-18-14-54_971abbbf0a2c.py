"""Default workflow_id=None for WorkflowExecution for test runs

Revision ID: 971abbbf0a2c
Revises: aff0128aa8f1
Create Date: 2025-03-18 14:54:56.003392

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "971abbbf0a2c"
down_revision = "aff0128aa8f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.alter_column(
            "workflow_id", existing_type=mysql.VARCHAR(length=255), nullable=True
        )


def downgrade() -> None:
    with op.batch_alter_table("workflowexecution", schema=None) as batch_op:
        batch_op.alter_column(
            "workflow_id", existing_type=mysql.VARCHAR(length=255), nullable=False
        )