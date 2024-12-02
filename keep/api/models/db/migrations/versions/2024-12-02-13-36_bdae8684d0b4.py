"""add lastalert and lastalerttoincident table

Revision ID: bdae8684d0b4
Revises: 3ad5308e7200
Create Date: 2024-11-05 22:48:04.733192

"""

import sqlalchemy as sa
import sqlalchemy_utils
import sqlmodel
from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "bdae8684d0b4"
down_revision = "3ad5308e7200"
branch_labels = None
depends_on = None

migration_metadata = sa.MetaData()


def populate_db():
    session = Session(op.get_bind())

    if session.bind.dialect.name == "postgresql":
        migrate_lastalert_query = """
            insert into lastalert (tenant_id, fingerprint, alert_id, timestamp)
                select alert.tenant_id, alert.fingerprint, alert.id as alert_id, alert.timestamp
                from alert
                join (
                    select
                        alert.tenant_id, alert.fingerprint, max(alert.timestamp) as last_received
                    from alert
                    group by fingerprint, tenant_id
                ) as a ON alert.fingerprint = a.fingerprint and alert.timestamp = a.last_received and alert.tenant_id = a.tenant_id
            on conflict
                do nothing
        """

        migrate_lastalerttoincident_query = """
            insert into lastalerttoincident (incident_id, tenant_id, timestamp, fingerprint, is_created_by_ai, deleted_at)
                select  ati.incident_id, ati.tenant_id, ati.timestamp, lf.fingerprint, ati.is_created_by_ai, ati.deleted_at
                from alerttoincident as ati
                join
                    (
                    select alert.tenant_id, alert.id, alert.fingerprint
                    from alert
                    join (
                        select
                            alert.tenant_id, alert.fingerprint, max(alert.timestamp) as last_received
                        from alert
                        group by fingerprint, tenant_id
                    ) as a on alert.fingerprint = a.fingerprint and alert.timestamp = a.last_received and alert.tenant_id = a.tenant_id
                ) as lf on ati.alert_id = lf.id
            on conflict
                do nothing
        """

    else:
        migrate_lastalert_query = """
        INSERT INTO lastalert (tenant_id, fingerprint, alert_id, timestamp)
        SELECT
            grouped_alerts.tenant_id,
            grouped_alerts.fingerprint,
            MAX(grouped_alerts.alert_id) as alert_id,  -- Using MAX to consistently pick one alert_id
            grouped_alerts.timestamp
        FROM (
            select alert.tenant_id, alert.fingerprint, alert.id as alert_id, alert.timestamp
            from alert
            join (
                select
                    alert.tenant_id, alert.fingerprint, max(alert.timestamp) as last_received
                from alert
                group by fingerprint, tenant_id
            ) as a ON alert.fingerprint = a.fingerprint
                   and alert.timestamp = a.last_received
                   and alert.tenant_id = a.tenant_id
        ) as grouped_alerts
        GROUP BY grouped_alerts.tenant_id, grouped_alerts.fingerprint, grouped_alerts.timestamp;
"""

        migrate_lastalerttoincident_query = """
        REPLACE INTO lastalerttoincident (incident_id, tenant_id, timestamp, fingerprint, is_created_by_ai, deleted_at)
            select ati.incident_id, ati.tenant_id, ati.timestamp, lf.fingerprint, ati.is_created_by_ai, ati.deleted_at
            from alerttoincident as ati
            join
                (
                select alert.id, alert.fingerprint, alert.tenant_id
                from alert
                join (
                    select
                        alert.tenant_id,alert.fingerprint, max(alert.timestamp) as last_received
                    from alert
                    group by fingerprint, tenant_id
                ) as a on alert.fingerprint = a.fingerprint and alert.timestamp = a.last_received and alert.tenant_id = a.tenant_id
            ) as lf on ati.alert_id = lf.id;
    """

    session.execute(migrate_lastalert_query)
    session.execute(migrate_lastalerttoincident_query)


def upgrade() -> None:
    op.create_table(
        "lastalert",
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("alert_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alert.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "fingerprint"),
    )
    with op.batch_alter_table("lastalert", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_lastalert_timestamp"), ["timestamp"], unique=False
        )
        # Add index for the fingerprint column that will be referenced by foreign key
        batch_op.create_index("ix_lastalert_fingerprint", ["fingerprint"], unique=False)

    op.create_table(
        "lastalerttoincident",
        sa.Column(
            "incident_id",
            sqlalchemy_utils.types.uuid.UUIDType(binary=False),
            nullable=False,
        ),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_created_by_ai", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fingerprint"],
            ["lastalert.tenant_id", "lastalert.fingerprint"],
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incident.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "incident_id", "fingerprint", "deleted_at"),
    )

    populate_db()


def downgrade() -> None:
    op.drop_table("lastalerttoincident")
    with op.batch_alter_table("lastalert", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_lastalert_timestamp"))

    op.drop_table("lastalert")