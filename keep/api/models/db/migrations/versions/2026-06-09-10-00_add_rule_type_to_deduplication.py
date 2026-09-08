"""feat: add rule_type to AlertDeduplicationRule

Revision ID: a1b2c3d4e5f6
Revises: 67ff7efffed4
Create Date: 2026-06-09 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "67ff7efffed4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # All existing rules are migrated to rule_type="split" because that was
    # the initial purpose of the deduplication rules.
    #
    # ACTION REQUIRED after deploying: review your existing custom deduplication
    # rules. If any rule was created with the intent of correlating related
    # alerts rather than controlling alert identity, change its rule_type to
    # "correlate" via the UI.
    with op.batch_alter_table("alertdeduplicationrule") as batch_op:
        batch_op.add_column(
            sa.Column(
                "rule_type",
                sa.String(),
                nullable=False,
                server_default="split",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("alertdeduplicationrule") as batch_op:
        batch_op.drop_column("rule_type")
