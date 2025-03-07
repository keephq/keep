"""Crecreate topology tables with tenant_id in all keys and transfer data

Revision ID: aaec81b991bd
Revises: a82154690f35
Create Date: 2025-03-07 17:49:13.393091

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "aaec81b991bd"
down_revision = "a82154690f35"
branch_labels = None
depends_on = None

def transfer_data():
    session = Session(bind=op.get_bind())
    dialect = session.bind.dialect.name

    session.execute(sa.text("""
        INSERT INTO topologyservice (
            id, tenant_id, source_provider_id, repository, tags, service, environment, display_name, description, 
            team, email, slack, ip_address, mac_address, category, manufacturer, namespace, is_manual
        )  
        SELECT 
            id, tenant_id, source_provider_id, repository, tags, service, environment, display_name, description, 
            team, email, slack, ip_address, mac_address, category, manufacturer, namespace, is_manual 
        FROM topologyservice_tmp
    """))

    session.execute(sa.text("""
        INSERT INTO topologyapplication (id, tenant_id, name, description, repository) 
        SELECT id, tenant_id, name, description, repository FROM topologyapplication_tmp
    """))

    session.execute(sa.text("""
        INSERT INTO topologyserviceapplication (service_id, application_id, tenant_id) 
        SELECT tsa.service_id, tsa.application_id, ts.tenant_id FROM topologyserviceapplication_tmp as tsa
        JOIN topologyservice_tmp as ts ON tsa.service_id = ts.id
    """))

    if dialect == "sqlite":
        session.execute(sa.text("""
            INSERT INTO topologyservicedependency (id, service_id, depends_on_service_id, updated_at, protocol, tenant_id) 
            SELECT lower(
                hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-' || '4' ||
                substr(hex( randomblob(2)), 2) || '-' ||
                substr('AB89', 1 + (abs(random()) % 4) , 1)  ||
                substr(hex(randomblob(2)), 2) || '-' ||
                hex(randomblob(6))
              ) as id, tsd.service_id, tsd.depends_on_service_id, tsd.updated_at, tsd.protocol, ts.tenant_id
            FROM topologyservicedependency_tmp as tsd
            JOIN topologyservice_tmp as ts ON tsd.service_id = ts.id
        """))
    elif dialect == "postgres":
        session.execute(sa.text("""
            INSERT INTO topologyservicedependency (id, service_id, depends_on_service_id, updated_at, protocol, tenant_id) 
            SELECT gen_random_uuid() as id, tsd.service_id, tsd.depends_on_service_id, tsd.updated_at, tsd.protocol, ts.tenant_id
            FROM topologyservicedependency_tmp as tsd
            JOIN topologyservice_tmp as ts ON tsd.service_id = ts.id
        """))
    elif dialect == "mysql":
        session.execute(sa.text("""
            INSERT INTO topologyservicedependency (id, service_id, depends_on_service_id, updated_at, protocol, tenant_id) 
            SELECT uuid() as id, tsd.service_id, tsd.depends_on_service_id, tsd.updated_at, tsd.protocol, ts.tenant_id
            FROM topologyservicedependency_tmp as tsd
            JOIN topologyservice_tmp as ts ON tsd.service_id = ts.id
        """))


def transfer_data_back():
    session = Session(bind=op.get_bind())

    session.execute(sa.text("""
        INSERT INTO topologyservice (
            id, tenant_id, source_provider_id, repository, tags, service, environment, display_name, description, 
            team, email, slack, ip_address, mac_address, category, manufacturer, namespace, is_manual
        )
        SELECT id, tenant_id, source_provider_id, repository, tags, service, environment, display_name, description, 
        team, email, slack, ip_address, mac_address, category, manufacturer, namespace, is_manual 
        FROM topologyservice_tmp
    """))

    session.execute(sa.text("""
        INSERT INTO topologyapplication (id, tenant_id, name, description, repository) 
        SELECT id, tenant_id, name, description, repository FROM topologyapplication_tmp
    """))

    session.execute(sa.text("""
        INSERT INTO topologyserviceapplication (service_id, application_id) 
        SELECT service_id, application_id FROM topologyserviceapplication_tmp
    """))

    session.execute(sa.text("""
        INSERT INTO topologyservicedependency (service_id, depends_on_service_id, updated_at, protocol) 
        SELECT service_id, depends_on_service_id, updated_at, protocol FROM topologyservicedependency_tmp
    """))

def upgrade():
    op.rename_table('topologyapplication', 'topologyapplication_tmp')
    op.rename_table('topologyservice', 'topologyservice_tmp')
    op.rename_table('topologyserviceapplication', 'topologyserviceapplication_tmp')
    op.rename_table('topologyservicedependency', 'topologyservicedependency_tmp')

    op.create_table(
        "topologyapplication",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("repository", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id", "tenant_id"),
    )
    op.create_table(
        "topologyservice",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "source_provider_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("repository", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("service", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("environment", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("display_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("team", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("slack", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("ip_address", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("mac_address", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("manufacturer", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("namespace", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("is_manual", sa.Boolean(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id", "tenant_id"),
    )
    op.create_table(
        "topologyserviceapplication",
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id", "tenant_id"],
            ["topologyapplication.id", "topologyapplication.tenant_id"],
        ),
        sa.ForeignKeyConstraint(
            ["service_id", "tenant_id"],
            ["topologyservice.id", "topologyservice.tenant_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "service_id", "application_id"),
    )
    op.create_table(
        "topologyservicedependency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("depends_on_service_id", sa.Integer(), nullable=False),
        sa.Column("protocol", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_service_id", "tenant_id"],
            ["topologyservice.id", "topologyservice.tenant_id"],
            name="topologyservicedependency_depends_on_service_id_tenant_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["service_id", "tenant_id"],
            ["topologyservice.id", "topologyservice.tenant_id"],
            name="topologyservicedependency_service_id_tenant_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id", "tenant_id"),
    )

    transfer_data()

    op.drop_table("topologyservicedependency_tmp")
    op.drop_table("topologyserviceapplication_tmp")
    op.drop_table("topologyapplication_tmp")
    op.drop_table("topologyservice_tmp")


def downgrade():

    op.rename_table('topologyapplication', 'topologyapplication_tmp')
    op.rename_table('topologyservice', 'topologyservice_tmp')
    op.rename_table('topologyserviceapplication', 'topologyserviceapplication_tmp')
    op.rename_table('topologyservicedependency', 'topologyservicedependency_tmp')

    op.create_table(
        "topologyapplication",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("repository", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "topologyservice",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "source_provider_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("repository", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("service", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("environment", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("display_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("team", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("slack", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("ip_address", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("mac_address", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("manufacturer", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("namespace", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("is_manual", sa.Boolean(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "topologyserviceapplication",
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["topologyapplication.id"],
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["topologyservice.id"],
        ),
        sa.PrimaryKeyConstraint("service_id", "application_id"),
    )
    op.create_table(
        "topologyservicedependency",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=True),
        sa.Column("depends_on_service_id", sa.Integer(), nullable=True),
        sa.Column("protocol", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_service_id"], ["topologyservice.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["topologyservice.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    transfer_data_back()

    op.drop_table("topologyservicedependency_tmp")
    op.drop_table("topologyserviceapplication_tmp")
    op.drop_table("topologyapplication_tmp")
    op.drop_table("topologyservice_tmp")
