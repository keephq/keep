"""Index workflow execution log lookups for bounded history maintenance.

Revision ID: 6942a1b2c3d4
Revises: 67ff7efffed4
Create Date: 2026-11-12 13:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = "6942a1b2c3d4"
down_revision = "67ff7efffed4"
branch_labels = None
depends_on = None

INDEX = "idx_workflowexecutionlog_workflow_execution_id"
TABLE = "workflowexecutionlog"
COLUMN = "workflow_execution_id"


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        indexes = (
            connection.execute(
                sa.text(
                    """
            SELECT index_relation.relname AS name, index_info.indisvalid AS valid,
                   index_info.indisready AS ready, index_info.indpred IS NULL AS full_index,
                   attribute.attname AS first_column
            FROM pg_index index_info
            JOIN pg_class index_relation ON index_relation.oid = index_info.indexrelid
            LEFT JOIN pg_attribute attribute ON attribute.attrelid = index_info.indrelid
                AND attribute.attnum = index_info.indkey[0]
            WHERE index_info.indrelid = to_regclass('workflowexecutionlog')
        """
                )
            )
            .mappings()
            .all()
        )
        for index in indexes:
            if index["name"] == INDEX and not (
                index["valid"]
                and index["ready"]
                and index["full_index"]
                and index["first_column"] == COLUMN
            ):
                raise RuntimeError(
                    f"Inspect/repair {INDEX} before retrying: it is invalid or has a different definition"
                )
        if any(
            index["valid"]
            and index["ready"]
            and index["full_index"]
            and index["first_column"] == COLUMN
            for index in indexes
        ):
            return
        # Existing large installations may prebuild this index before upgrading.
        # Never wrap CREATE INDEX CONCURRENTLY in the migration transaction.
        with op.get_context().autocommit_block():
            op.create_index(INDEX, TABLE, [COLUMN], postgresql_concurrently=True)
    else:
        indexes = sa.inspect(connection).get_indexes(TABLE)
        if any(
            index["column_names"]
            and index["column_names"][0] == COLUMN
            and index.get("dialect_options", {}).get("sqlite_where") is None
            for index in indexes
        ):
            return
        op.create_index(INDEX, TABLE, [COLUMN])


def downgrade():
    connection = op.get_bind()
    if not any(
        index["name"] == INDEX for index in sa.inspect(connection).get_indexes(TABLE)
    ):
        return
    if connection.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(INDEX, table_name=TABLE, postgresql_concurrently=True)
    else:
        op.drop_index(INDEX, table_name=TABLE)
