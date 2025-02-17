"""WF index

Revision ID: 90e2d22edc6a
Revises: 7fde94be79e4
Create Date: 2025-02-13 17:27:56.350500

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "90e2d22edc6a"
down_revision = "7fde94be79e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    try:
        conn.execute(
            text("COMMIT")
        )  # Close existing transaction, otherwise it will fail on PG on the next step
    except Exception:
        pass  # No transaction to commit

    try:
        op.create_index(
            "idx_status_started", 
            "workflowexecution", 
            [("status", text("255")), "started"]
        )
    except Exception as e:
        if "already exists" not in str(e):
            raise e
        else:
            print("Index idx_status_started already exists. It's ok.")


def downgrade() -> None:
    op.drop_index("idx_status_started", table_name="workflowexecution")
