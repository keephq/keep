"""empty message

Revision ID: 78777e6b12d3
Revises: bdf252fbc1be, 0dafe96ea97f
Create Date: 2025-04-06 12:18:21.809822

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "78777e6b12d3"
down_revision = ("bdf252fbc1be", "0dafe96ea97f")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
