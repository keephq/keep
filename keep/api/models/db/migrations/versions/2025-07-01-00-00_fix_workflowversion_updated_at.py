"""fix: remove onupdate from WorkflowVersion.updated_at to preserve revision timestamps

Revision ID: fix_workflowversion_updated_at
Revises: 9dd1be4539e0
Create Date: 2025-07-01 00:00:00.000000

The `updated_at` column on `workflowversion` had `ON UPDATE CURRENT_TIMESTAMP`
(expressed via SQLAlchemy's `onupdate=func.now()`).  This caused every existing
revision row to have its timestamp silently overwritten whenever any column on
that row was updated — most notably when `is_current` was flipped to False on
all revisions before inserting a new one.  The result was that every revision
in the Versions panel showed the timestamp of the most-recent save.

This migration replaces the column definition with one that only sets a default
on INSERT, so once a revision row is created its `updated_at` is immutable.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "fix_workflowversion_updated_at"
down_revision = "9dd1be4539e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Re-define the column without ON UPDATE so existing timestamps are frozen.
    # We use batch_alter_table for SQLite compatibility.
    with op.batch_alter_table("workflowversion", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            # Explicitly do NOT set onupdate — this is the whole point of the fix.
            nullable=False,
        )


def downgrade() -> None:
    # Restore the original (buggy) ON UPDATE behaviour.
    with op.batch_alter_table("workflowversion", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.FetchedValue(),
            nullable=False,
        )
