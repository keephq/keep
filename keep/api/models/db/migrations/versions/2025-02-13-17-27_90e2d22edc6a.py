"""WF index

Revision ID: 90e2d22edc6a
Revises: 8176d7153747
Create Date: 2025-02-13 17:27:56.350500

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "90e2d22edc6a"
down_revision = "8176d7153747"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect_name = op.get_context().dialect.name

    try:
        conn.execute(
            text("COMMIT")
        )  # Close existing transaction, otherwise it will fail on PG on the next step
    except Exception:
        pass  # No transaction to commit

    try:
        if dialect_name == "mysql":
            # MySQL allows/requires length for string columns in indexes
            op.create_index(
                "idx_status_started",
                "workflowexecution",
                [(text("status(255)")), "started"],
            )
        else:
            # PostgreSQL and SQLite don't need/support length specifications
            op.create_index(
                "idx_status_started", "workflowexecution", ["status", "started"]
            )
    except Exception as e:
        if "already exists" not in str(e):
            raise e
        else:
            print("Index idx_status_started already exists. It's ok.")


def downgrade() -> None:
    op.drop_index("idx_status_started", table_name="workflowexecution")
