"""empty message

Revision ID: d359baaf0836
Revises: 8a4ec08f2d6b, e3f33e571c3c
Create Date: 2025-01-19 10:44:47.871555

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "d359baaf0836"
down_revision = ("8a4ec08f2d6b", "e3f33e571c3c")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
