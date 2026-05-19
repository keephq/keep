"""Add ondelete CASCADE to TopologyServiceApplication foreign keys

Revision ID: a1b2c3d4e5f6
Revises: 9dd1be4539e0
Create Date: 2026-05-12 04:50:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9dd1be4539e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing FK constraints and recreate with ondelete=CASCADE
    # FK on service_id -> topologyservice.id
    op.drop_constraint(
        "topologyserviceapplication_service_id_fkey",
        "topologyserviceapplication",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "topologyserviceapplication_service_id_fkey",
        "topologyserviceapplication",
        "topologyservice",
        ["service_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # FK on application_id -> topologyapplication.id
    op.drop_constraint(
        "topologyserviceapplication_application_id_fkey",
        "topologyserviceapplication",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "topologyserviceapplication_application_id_fkey",
        "topologyserviceapplication",
        "topologyapplication",
        ["application_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Revert to no ondelete
    op.drop_constraint(
        "topologyserviceapplication_service_id_fkey",
        "topologyserviceapplication",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "topologyserviceapplication_service_id_fkey",
        "topologyserviceapplication",
        "topologyservice",
        ["service_id"],
        ["id"],
    )
    op.drop_constraint(
        "topologyserviceapplication_application_id_fkey",
        "topologyserviceapplication",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "topologyserviceapplication_application_id_fkey",
        "topologyserviceapplication",
        "topologyapplication",
        ["application_id"],
        ["id"],
    )
