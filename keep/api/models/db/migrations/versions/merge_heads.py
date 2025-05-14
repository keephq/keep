"""merge heads

Revision ID: merge_heads
Revises: combined_commentmention, 7b687c555318
Create Date: 2025-05-13 16:30:00.000000

"""

# revision identifiers, used by Alembic.
revision = 'merge_heads'
down_revision = None
branch_labels = None
depends_on = ('combined_commentmention', '7b687c555318')

from alembic import op
import sqlalchemy as sa


def upgrade():
    pass


def downgrade():
    pass
