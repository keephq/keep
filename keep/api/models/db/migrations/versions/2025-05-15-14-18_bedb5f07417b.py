"""merge heads "c2f78c69e9cf" and "fcef2c58b21c": Add threshold field to Rule + Recalculate alerts_count for incidents

Revision ID: bedb5f07417b
Revises: c2f78c69e9cf, fcef2c58b21c
Create Date: 2025-05-15 14:18:13.356729

"""

# revision identifiers, used by Alembic.
revision = "bedb5f07417b"
down_revision = ("c2f78c69e9cf", "fcef2c58b21c")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
