from alembic import op
import sqlalchemy as sa


def drop_foreign_key_constraint(table_name, column_name, referred_table):
    # First check if the column is nullable (for those who haven't migrated yet)
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    # Find the actual foreign key constraint name for workflow_id
    foreign_keys = inspector.get_foreign_keys(table_name)
    foreign_key = None
    for fk in foreign_keys:
        if (
            column_name in fk.get("constrained_columns", [])
            and fk.get("referred_table") == referred_table
        ):
            foreign_key = fk
            break

    fk_name = foreign_key.get("name") if foreign_key else None

    # Drop the foreign key constraint if it exists
    if fk_name:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")


def drop_primary_key_constraint(table_name):

