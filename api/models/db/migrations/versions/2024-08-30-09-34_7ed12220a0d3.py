"""Added is_disabled to workflows

Revision ID: 7ed12220a0d3
Revises: 1c650a429672
Create Date: 2024-08-30 09:34:41.782797

"""

import sqlalchemy as sa
import yaml
from alembic import op

from keep.parser.parser import Parser

# revision identifiers, used by Alembic.
revision = "7ed12220a0d3"
down_revision = "1c650a429672"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workflow", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default=sa.false()))

    connection = op.get_bind()
    workflows = connection.execute(sa.text("SELECT id, workflow_raw FROM workflow")).fetchall()

    updates = []
    for workflow in workflows:
        try:
            workflow_yaml = yaml.safe_load(workflow.workflow_raw)
            # If, by any chance, the existing workflow YAML's "disabled" value resolves to true,
            # we need to update the database to set `is_disabled` to `True`
            if Parser.parse_disabled(workflow_yaml):
                updates.append({
                    'id': workflow.id,
                    'is_disabled': True
                })
        except Exception as e:
            print(f"Failed to parse workflow_raw for workflow id {workflow.id}: {e}")
            continue

    if updates:
        connection.execute(
            sa.text(
                "UPDATE workflow SET is_disabled = :is_disabled WHERE id = :id"
            ),
            updates
        )



def downgrade() -> None:
    with op.batch_alter_table("workflow", schema=None) as batch_op:
        batch_op.drop_column("is_disabled")

    connection = op.get_bind()
    workflows = connection.execute(sa.text("SELECT id, workflow_raw FROM workflow")).fetchall()

    updates = []
    for workflow in workflows:
        try:
            workflow_yaml = yaml.safe_load(workflow.workflow_raw)
            if 'disabled' in workflow_yaml:
                workflow_yaml.pop('disabled', None)
                updated_workflow_raw = yaml.safe_dump(workflow_yaml)
                updates.append({
                    'id': workflow.id,
                    'workflow_raw': updated_workflow_raw
                })
        except Exception as e:
            print(f"Failed to parse workflow_raw for workflow id {workflow.id}: {e}")
            continue

    if updates:
        connection.execute(
            sa.text(
                "UPDATE workflow SET workflow_raw = :workflow_raw WHERE id = :id"
            ),
            updates
        )
