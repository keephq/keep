"""increase secret value column from VARCHAR to TEXT

Revision ID: a1b2c3d4e5f6
Revises: 9dd1be4539e0
Create Date: 2025-04-01 02:50:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9dd1be4539e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change `secret.value` from VARCHAR(255) to TEXT so that long OAuth tokens
    # (and other secrets exceeding 255 characters) are no longer silently truncated
    # when SECRET_MANAGER_TYPE=db is used.
    op.alter_column(
        "secret",
        "value",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    # WARNING: downgrading will truncate any values longer than 255 chars.
    op.alter_column(
        "secret",
        "value",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
