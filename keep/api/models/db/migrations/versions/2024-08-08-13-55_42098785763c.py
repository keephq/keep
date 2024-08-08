"""Merging 2 heads

Revision ID: 42098785763c
Revises: 67f1efb93c99, 4147d9e706c0
Create Date: 2024-08-08 13:55:55.191243

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "42098785763c"
down_revision = ("67f1efb93c99", "4147d9e706c0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
