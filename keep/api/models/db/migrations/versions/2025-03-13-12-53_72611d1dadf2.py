"""empty message

Revision ID: 72611d1dadf2
Revises: 9f11356d8ed9, aaec81b991bd
Create Date: 2025-03-13 12:53:16.705110

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "72611d1dadf2"
down_revision = ("9f11356d8ed9", "aaec81b991bd")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
