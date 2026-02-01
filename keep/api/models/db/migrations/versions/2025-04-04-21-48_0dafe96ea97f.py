"""auto delete provider logs

Revision ID: 0dafe96ea97f
Revises: e663a98b1142
Create Date: 2025-04-04 21:48:38.282584

"""

from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0dafe96ea97f"
down_revision = "e663a98b1142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name

    if dialect == "sqlite":
        # SQLite doesn't support ALTER TABLE for dropping constraints
        # Create a new table with the desired schema, move data, drop old table, rename new table

        # Get table info
        conn = op.get_bind()
        inspector = inspect(conn)
        columns = inspector.get_columns("providerexecutionlog")
        column_definitions = []

        # Recreate column definitions
        for column in columns:
            # Make provider_id nullable
            if column["name"] == "provider_id":
                column["nullable"] = True

            column_type = column["type"]
            nullable = "NULL" if column["nullable"] else "NOT NULL"
            default = (
                f"DEFAULT {column['default']}"
                if column.get("default") is not None
                else ""
            )

            column_def = f"{column['name']} {column_type} {nullable} {default}".strip()
            column_definitions.append(column_def)

        # Create new table with foreign key constraint included
        primary_keys = []
        for column in columns:
            if column.get("primary_key", False):
                primary_keys.append(column["name"])

        # Need to include primary key and foreign key in table creation
        primary_key_clause = (
            f", PRIMARY KEY ({', '.join(primary_keys)})" if primary_keys else ""
        )

        op.execute(
            f"""
        CREATE TABLE providerexecutionlog_new (
            {", ".join(column_definitions)}{primary_key_clause},
            FOREIGN KEY (provider_id) REFERENCES provider(id) ON DELETE CASCADE
        )
        """
        )

        # Copy data
        op.execute(
            """
        INSERT INTO providerexecutionlog_new
        SELECT * FROM providerexecutionlog
        """
        )

        # Drop old table
        op.drop_table("providerexecutionlog")

        # Rename new table
        op.rename_table("providerexecutionlog_new", "providerexecutionlog")

        # No need to separately add foreign key as it's included in table creation
    else:
        # PostgreSQL and MySQL support
        with op.batch_alter_table("providerexecutionlog", schema=None) as batch_op:
            batch_op.alter_column(
                "provider_id", existing_type=mysql.VARCHAR(length=255), nullable=True
            )
            if dialect == "postgresql":
                batch_op.drop_constraint(
                    "providerexecutionlog_provider_id_fkey", type_="foreignkey"
                )
            else:
                batch_op.drop_constraint(
                    "providerexecutionlog_ibfk_1", type_="foreignkey"
                )
            batch_op.create_foreign_key(
                None, "provider", ["provider_id"], ["id"], ondelete="CASCADE"
            )

    # ### end Alembic commands ###


def downgrade() -> None:
    dialect = op.get_context().dialect.name

    if dialect == "sqlite":
        # For SQLite, recreate the table again without CASCADE
        # Get table info
        conn = op.get_bind()
        inspector = inspect(conn)
        columns = inspector.get_columns("providerexecutionlog")
        column_definitions = []

        # Recreate column definitions
        for column in columns:
            # Make provider_id NOT NULL
            if column["name"] == "provider_id":
                column["nullable"] = False

            column_type = column["type"]
            nullable = "NULL" if column["nullable"] else "NOT NULL"
            default = (
                f"DEFAULT {column['default']}"
                if column.get("default") is not None
                else ""
            )

            column_def = f"{column['name']} {column_type} {nullable} {default}".strip()
            column_definitions.append(column_def)

        # Create new table with foreign key constraint included
        primary_keys = []
        for column in columns:
            if column.get("primary_key", False):
                primary_keys.append(column["name"])

        # Need to include primary key and foreign key in table creation
        primary_key_clause = (
            f", PRIMARY KEY ({', '.join(primary_keys)})" if primary_keys else ""
        )

        op.execute(
            f"""
        CREATE TABLE providerexecutionlog_new (
            {", ".join(column_definitions)}{primary_key_clause},
            FOREIGN KEY (provider_id) REFERENCES provider(id)
        )
        """
        )

        # Copy data
        op.execute(
            """
        INSERT INTO providerexecutionlog_new
        SELECT * FROM providerexecutionlog
        """
        )

        # Drop old table
        op.drop_table("providerexecutionlog")

        # Rename new table
        op.rename_table("providerexecutionlog_new", "providerexecutionlog")

        # No need to separately add foreign key as it's included in table creation
    else:
        # PostgreSQL and MySQL downgrade
        with op.batch_alter_table("providerexecutionlog", schema=None) as batch_op:
            batch_op.drop_constraint(None, type_="foreignkey")
            if dialect == "postgresql":
                batch_op.create_foreign_key(
                    "providerexecutionlog_provider_id_fkey",
                    "provider",
                    ["provider_id"],
                    ["id"],
                )
            else:
                batch_op.create_foreign_key(
                    "providerexecutionlog_ibfk_1", "provider", ["provider_id"], ["id"]
                )
            batch_op.alter_column(
                "provider_id", existing_type=mysql.VARCHAR(length=255), nullable=False
            )
    # ### end Alembic commands ###
