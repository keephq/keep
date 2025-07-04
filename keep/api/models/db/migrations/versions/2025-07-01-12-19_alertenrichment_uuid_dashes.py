"""Remove dashes from alert_fingerprint UUIDs for mysql and sqlite

Revision ID: 613f4a584f37
Revises: 9dd1be4539e0
Create Date: 2025-07-01 12:19:08.895646

We look up incident enrichments using cast(alert_fingerprint as char). MySQL casts uuid to varchar without dashes. However, until now we used Python's `str()` to cast the uuid to a string when creating the incident enrichment, resulting in enrichments not found. This migration removes the dashes from previous entries.

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "613f4a584f37"
down_revision = "9dd1be4539e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        pass
    elif dialect == "mysql":
        # for mysql find all uuid strings and replace the dashes with empty strings, as mysql casts uuid to varchar without dashes,
        op.execute(
            """UPDATE IGNORE alertenrichment 
            SET alert_fingerprint = REPLACE(alert_fingerprint, '-', '')
            WHERE CHAR_LENGTH(alert_fingerprint) = 36 
            AND alert_fingerprint REGEXP '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$';
            """
        )
    elif dialect == "sqlite":
        op.execute(
            """UPDATE or IGNORE alertenrichment 
            SET alert_fingerprint = REPLACE(alert_fingerprint, '-', '')
            WHERE LENGTH(alert_fingerprint) = 36 
            AND alert_fingerprint REGEXP '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
            """
        )
    pass


def downgrade() -> None:
    pass
