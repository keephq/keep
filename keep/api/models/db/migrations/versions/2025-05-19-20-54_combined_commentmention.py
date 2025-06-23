"""Add CommentMention table with proper cascade delete

Revision ID: combined_commentmention
Revises: aa167915c4d6
Create Date: 2025-05-19 20:54:00.000000

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "combined_commentmention"
down_revision = "aa167915c4d6"  # Same as the original parent
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if the commentmention table already exists
    conn = op.get_bind()
    inspector = inspect(conn)
    if "commentmention" not in inspector.get_table_names():
        # Create the CommentMention table for storing user mentions in comments with CASCADE delete
        op.create_table(
            "commentmention",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("comment_id", sa.Uuid(), nullable=False),
            sa.Column(
                "mentioned_user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
            ),
            sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["comment_id"],
                ["alertaudit.id"],
                name="fk_commentmention_alertaudit_cascade",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"],
                ["tenant.id"],
                name="fk_commentmention_tenant",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_commentmention"),
            sa.UniqueConstraint(
                "comment_id", "mentioned_user_id", name="uq_comment_mention"
            ),
        )

        # Create indexes
        op.create_index(
            "ix_comment_mention_comment_id",
            "commentmention",
            ["comment_id"],
            unique=False,
        )
        op.create_index(
            "ix_comment_mention_mentioned_user_id",
            "commentmention",
            ["mentioned_user_id"],
            unique=False,
        )
        op.create_index(
            "ix_comment_mention_tenant_id",
            "commentmention",
            ["tenant_id"],
            unique=False,
        )


def downgrade() -> None:
    # Drop the table if it exists
    conn = op.get_bind()
    inspector = inspect(conn)
    if "commentmention" in inspector.get_table_names():
        op.drop_table("commentmention")
