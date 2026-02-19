"""Add is_predicted and is_confirmed flags to Incident model

Revision ID: dcbd2873dcfd
Revises: 37019ca3eb2e
Create Date: 2024-07-17 16:46:59.386127

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import expression

# revision identifiers, used by Alembic.
revision = "dcbd2873dcfd"
down_revision = "37019ca3eb2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incident",
        sa.Column(
            "is_confirmed",
            sa.Boolean(),
            nullable=False,
            default=False,
            server_default=expression.false(),
        ),
    )
    op.add_column(
        "incident",
        sa.Column(
            "is_predicted",
            sa.Boolean(),
            nullable=False,
            default=False,
            server_default=expression.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("incident", "is_confirmed")
    op.drop_column("incident", "is_predicted")
