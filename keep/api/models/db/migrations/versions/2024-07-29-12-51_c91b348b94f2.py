"""Description replaced w/ user_summary

Revision ID: c91b348b94f2
Revises: 8e5942040de6
Create Date: 2024-07-29 12:51:24.496126

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "c91b348b94f2"
down_revision = "8e5942040de6"
branch_labels = None
depends_on = None


# Define a completely separate metadata for the migration
migration_metadata = sa.MetaData()

# Direct table definition for Incident
incident_table = sa.Table(
    "incident",
    migration_metadata,
    sa.Column("id", UUID(as_uuid=False), primary_key=True),
    sa.Column("description", sa.String),
    sa.Column("user_summary", sa.String),
)


def populate_db(session):
    # we need to populate the user_summary field with the description
    session.execute(
        sa.update(incident_table).values(user_summary=incident_table.c.description)
    )
    session.commit()


def depopulate_db(session):
    # we need to populate the description field with the user_summary
    session.execute(
        sa.update(incident_table).values(description=incident_table.c.user_summary)
    )
    session.commit()


def upgrade() -> None:
    # First ensure data is copied
    session = Session(op.get_bind())
    populate_db(session)

    # Then drop the column using batch_alter_table for SQLite compatibility
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.drop_column("description")


def downgrade() -> None:
    # First add the description column back
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "description", 
                sa.VARCHAR(), 
                nullable=False, 
                server_default=""
            )
        )
    
    # Copy the data from user_summary to description
    session = Session(op.get_bind())
    depopulate_db(session)

    # Finally drop the user_summary column
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.drop_column("user_summary")
