"""Fix wrong rule.resolve_on values

Revision ID: e343054ae740
Revises: d359baaf0836
Create Date: 2025-02-05 15:46:25.933229

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "e343054ae740"
down_revision = "d359baaf0836"
branch_labels = None
depends_on = None

def populate_db():
    session = Session(op.get_bind())

    session.execute(
        text("""
            UPDATE rule
            SET resolve_on = 'all_resolved'
            WHERE resolve_on = 'all'
        """))

    session.execute(
        text("""
            UPDATE rule
            SET resolve_on = 'first_resolved'
            WHERE resolve_on = 'first'
        """))

    session.execute(
        text("""
            UPDATE rule
            SET resolve_on = 'last_resolved'
            WHERE resolve_on = 'last'
        """))

def upgrade() -> None:
    populate_db()


def downgrade() -> None:
    pass
