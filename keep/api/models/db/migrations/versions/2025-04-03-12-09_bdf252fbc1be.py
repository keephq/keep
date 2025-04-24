"""json_for_dashboard_config

Revision ID: bdf252fbc1be
Revises: e663a98b1142
Create Date: 2025-04-03 12:09:19.911725

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "bdf252fbc1be"
down_revision = "e663a98b1142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    if conn.dialect.name == "postgresql":
        result = conn.execute(
            sa.text(
                "SELECT data_type FROM information_schema.columns WHERE table_name='dashboard' AND column_name='dashboard_config';"
            )
        ).fetchone()
        if result and result[0] != "json":
            conn.execute(
                sa.text(
                    "ALTER TABLE dashboard ALTER COLUMN dashboard_config TYPE JSON USING dashboard_config::json;"
                )
            )

    elif conn.dialect.name == "mysql":
        result = conn.execute(
            sa.text("SHOW COLUMNS FROM dashboard WHERE Field='dashboard_config';")
        ).fetchone()
        if result and "json" not in result[1].lower():
            op.alter_column("dashboard", "dashboard_config", type_=mysql.JSON)


def downgrade() -> None:
    conn = op.get_bind()

    if conn.dialect.name == "postgresql":
        result = conn.execute(
            sa.text(
                "SELECT data_type FROM information_schema.columns WHERE table_name='dashboard' AND column_name='dashboard_config';"
            )
        ).fetchone()
        if result and result[0] == "json":
            op.alter_column("dashboard", "dashboard_config", type_=sa.Text)

    elif conn.dialect.name == "mysql":
        result = conn.execute(
            sa.text("SHOW COLUMNS FROM dashboard WHERE Field='dashboard_config';")
        ).fetchone()
        if result and "json" in result[1].lower():
            op.alter_column("dashboard", "dashboard_config", type_=sa.Text)
