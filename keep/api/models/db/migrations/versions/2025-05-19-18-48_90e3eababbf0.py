"""empty message

Revision ID: 90e3eababbf0
Revises: combined_commentmention, aa167915c4d6
Create Date: 2025-05-19 18:48:20.899302

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "90e3eababbf0"
down_revision = ("combined_commentmention", "aa167915c4d6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
