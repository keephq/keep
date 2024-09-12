"""empty message

Revision ID: 9af44b2de182
Revises: 772790c2e50a, 710b4ff1d19e
Create Date: 2024-09-12 14:26:29.985470

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "9af44b2de182"
down_revision = ("772790c2e50a", "710b4ff1d19e")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
