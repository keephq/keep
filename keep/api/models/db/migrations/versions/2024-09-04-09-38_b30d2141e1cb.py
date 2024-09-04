"""Merge migrations to resolve double-headed issue

Revision ID: b30d2141e1cb
Revises: 7ed12220a0d3, 49e7c02579db
Create Date: 2024-09-04 09:38:33.869973

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "b30d2141e1cb"
down_revision = ("7ed12220a0d3", "49e7c02579db")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
