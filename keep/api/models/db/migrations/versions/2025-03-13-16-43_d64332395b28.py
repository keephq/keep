"""empty message

Revision ID: d64332395b28
Revises: aaec81b991bd, c0e70149c9ec
Create Date: 2025-03-13 16:43:42.827477

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "d64332395b28"
down_revision = ("aaec81b991bd", "c0e70149c9ec")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
