"""Add_unique_constraint_for_alert_fingerprint_and_tenant_id

Revision ID: 16309df224d1
Revises: 0b80bda47ee2
Create Date: 2025-03-11 16:54:14.972144

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op
from sqlalchemy.dialects import mysql, postgresql

# revision identifiers, used by Alembic.
revision = "16309df224d1"
down_revision = "0b80bda47ee2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    # Step 1: Drop the old unique constraint on alert_fingerprint
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "mysql":
        try:
            op.drop_constraint("alert_fingerprint", "alertenrichment", type_="unique")
        except Exception:
            # ignore because this constraint may not exist
            pass

        with op.batch_alter_table("alertenrichment") as batch_op:
            batch_op.create_unique_constraint(
                "uc_alertenrichment_tenant_fingerprint",
                ["tenant_id", "alert_fingerprint"],
            )

        # Step 2: Remove duplicates (keep the oldest row per tenant_id, alert_fingerprint)
        op.execute(
            """
            WITH duplicates AS (
                SELECT id,
                    ROW_NUMBER() OVER (
                        PARTITION BY tenant_id, alert_fingerprint 
                        ORDER BY timestamp DESC
                    ) AS rn
                FROM alertenrichment
            )
            DELETE FROM alertenrichment
            WHERE id IN (SELECT id FROM duplicates WHERE rn > 1);
        """
        )

    elif dialect == "postgresql":
        op.drop_constraint("alert_fingerprint", "alertenrichment", type_="unique")
        with op.batch_alter_table("alertenrichment") as batch_op:
            batch_op.create_unique_constraint(
                "uc_alertenrichment_tenant_fingerprint",
                ["tenant_id", "alert_fingerprint"],
            )
    elif dialect == "sqlite":
        op.create_table(
            "alertenrichment_new",
            sa.Column("enrichments", sa.JSON(), nullable=True),
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column(
                "alert_fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=False
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"],
                ["tenant.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )

        # Copy existing data
        op.execute(
            """
            INSERT INTO alertenrichment_new (id, tenant_id, alert_fingerprint, timestamp, enrichments)
            SELECT id, tenant_id, alert_fingerprint, timestamp, enrichments FROM alertenrichment;
        """
        )

        # Drop the old table and rename the new one
        op.execute("DROP TABLE alertenrichment;")
        op.execute("ALTER TABLE alertenrichment_new RENAME TO alertenrichment;")
        with op.batch_alter_table("alertenrichment") as batch_op:
            batch_op.create_unique_constraint(
                "uc_alertenrichment_tenant_fingerprint",
                ["tenant_id", "alert_fingerprint"],
            )

    # Step 3: Add the new composite unique constraint

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    # Step 1: Drop the new unique constraint

    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "mysql":
        op.execute(
            "ALTER TABLE alertenrichment DROP FOREIGN KEY alertenrichment_ibfk_1;"
        )

        op.drop_constraint(
            "uc_alertenrichment_tenant_fingerprint", "alertenrichment", type_="unique"
        )
        op.execute(
            """
            ALTER TABLE alertenrichment
            ADD CONSTRAINT alertenrichment_ibfk_1
            FOREIGN KEY (tenant_id) 
            REFERENCES tenant(id)
            ON DELETE CASCADE ON UPDATE CASCADE;
        """
        )
        op.create_unique_constraint(
            "alert_fingerprint", "alertenrichment", ["alert_fingerprint"]
        )

    elif dialect == "postgresql":
        op.drop_constraint(
            "uc_alertenrichment_tenant_fingerprint", "alertenrichment", type_="unique"
        )
        op.create_unique_constraint(
            "alert_fingerprint", "alertenrichment", ["alert_fingerprint"]
        )

    elif dialect == "sqlite":
        op.create_table(
            "alertenrichment_new",
            sa.Column("enrichments", sa.JSON(), nullable=True),
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column(
                "alert_fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=False
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"],
                ["tenant.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("alert_fingerprint"),
        )

        # Copy existing data
        op.execute(
            """
            INSERT INTO alertenrichment_new (id, tenant_id, alert_fingerprint, timestamp, enrichments)
            SELECT id, tenant_id, alert_fingerprint, timestamp, enrichments FROM alertenrichment;
        """
        )

        # Drop the old table and rename the new one
        op.execute("DROP TABLE alertenrichment;")
        op.execute("ALTER TABLE alertenrichment_new RENAME TO alertenrichment;")

    # Step 2: Restore the old unique constraint on alert_fingerprint

    # ### end Alembic commands ###
