"""Alert To Incident link history

Revision ID: 83c1020be97d
Revises: bf756df80e9d
Create Date: 2024-10-14 08:34:46.608806

"""

from sqlalchemy import inspect
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import expression
from contextlib import contextmanager

# revision identifiers, used by Alembic.
revision = "83c1020be97d"
down_revision = "bf756df80e9d"
branch_labels = None
depends_on = None


@contextmanager
def drop_and_restore_f_keys(table_name, conn):
    inspector = inspect(conn)
    existing_f_keys = inspector.get_foreign_keys(table_name, schema=None)

    print(f"Existing foreign keys: {existing_f_keys}")

    # Drop all foreign keys
    for fk in existing_f_keys:
        try:
            op.drop_constraint(fk['name'], table_name, type_='foreignkey')
            print(f"Dropped foreign key: {fk['name']}")
        except NotImplementedError as e:
            if "No support for ALTER of constraints in SQLite dialect." in str(e):
                print("No support for ALTER of constraints in SQLite dialect, constraint should be overriden later so skipping")
            else:
                raise e
    try:
        yield
    finally:
        # Restore all foreign keys
        for fk in existing_f_keys:
            try:
                op.create_foreign_key(
                    fk['name'],
                    table_name,
                    fk['referred_table'],
                    fk['constrained_columns'],
                    fk['referred_columns'],
                    ondelete=fk['options'].get('ondelete')
                )
                print(f"Restored foreign key: {fk['name']}")
            except NotImplementedError as e:
                if "No support for ALTER of constraints in SQLite dialect." in str(e):
                    print("No support for ALTER of constraints in SQLite dialect, constraint should be overriden later so skipping")
                else:
                    raise e


def upgrade() -> None:
    with op.batch_alter_table("alerttoincident", schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            "is_created_by_ai", 
            sa.Boolean(), 
            nullable=False, 
            server_default=expression.false()
        ))
        batch_op.add_column(sa.Column(
            "deleted_at",
            sa.DateTime(), 
            nullable=False,
            server_default="1000-01-01 00:00:00",
        ))

    conn = op.get_bind()

    with drop_and_restore_f_keys("alerttoincident", conn):
        try:
            with op.batch_alter_table("alerttoincident", schema=None) as batch_op:
                inspector = inspect(conn)
                existing_primary_key = inspector.get_pk_constraint('alerttoincident', schema=None)
                batch_op.drop_constraint(existing_primary_key['name'], type_="primary")
        except ValueError as e:
            if "Constraint must have a name" in str(e):
                print("Constraint must have a name, constraint should be overriden later so skipping")
            else:
                raise e

        with op.batch_alter_table("alerttoincident", schema=None) as batch_op:
            batch_op.create_primary_key(
                "alerttoincident_pkey", ["alert_id", "incident_id", "deleted_at"]
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    existing_primary_key = inspector.get_pk_constraint('alerttoincident', schema=None)

    with op.batch_alter_table("alerttoincident", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_created_by_ai")

    with drop_and_restore_f_keys("alerttoincident", conn):
        with op.batch_alter_table("alerttoincident", schema=None) as batch_op:
            batch_op.drop_constraint(existing_primary_key['name'], type_="primary")
        with op.batch_alter_table("alerttoincident", schema=None) as batch_op:
            batch_op.create_primary_key(
                "alerttoincident_pkey", ["alert_id", "incident_id"]
            )
