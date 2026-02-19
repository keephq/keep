"""“add-counter_shows_firing_only-column-for-preset”

Revision ID: e663a98b1142
Revises: 2a6132b443ab
Create Date: 2025-03-30 10:53:31.773788

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e663a98b1142"
down_revision = "2a6132b443ab"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "preset",
        sa.Column(
            "counter_shows_firing_only",
            sa.Boolean(),
            nullable=True,  # make it nullable to avoid issues with old rows
            server_default=sa.false(),  # default value for new rows
        ),
    )


def downgrade():
    op.drop_column("preset", "counter_shows_firing_only")
