"""empty message

Revision ID: eeae12935acd
Revises: add_incident_comments, 7b687c555318
Create Date: 2025-05-12 12:44:15.300078

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "eeae12935acd"
down_revision = ("add_incident_comments", "7b687c555318")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
