"""Crecreate topology tables with tenant_id in all keys and transfer data

Revision ID: aaec81b991bd
Revises: 0b80bda47ee2
Create Date: 2025-03-07 17:49:13.393091

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "aaec81b991bd"
down_revision = "0b80bda47ee2"
branch_labels = None
depends_on = None

def transfer_data():
    session = Session(bind=op.get_bind())
    dialect = session.bind.dialect.name

    uuid_generation_func = "replace(uuid(),'-','')"
    if dialect == "sqlite":
        uuid_generation_func = """
        lower(
            hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-' || '4' ||
            substr(hex( randomblob(2)), 2) || '-' ||
            substr('AB89', 1 + (abs(random()) % 4) , 1)  ||
            substr(hex(randomblob(2)), 2) || '-' ||
            hex(randomblob(6))
          )
        """
    elif dialect == "postgresql":
        uuid_generation_func = "gen_random_uuid()"

    session.execute(sa.text(f"""
        INSERT INTO topologyservice (
            id, external_id, tenant_id, source_provider_id, repository, tags, service, environment, display_name, description, 
            team, email, slack, ip_address, mac_address, category, manufacturer, namespace, is_manual
        )  
        SELECT 
            {uuid_generation_func} as id, id as external_id, tenant_id, source_provider_id, repository, tags, service, environment, display_name, description, 
            team, email, slack, ip_address, mac_address, category, manufacturer, namespace, is_manual 
        FROM topologyservice_tmp
    """))

    session.execute(sa.text("""
        INSERT INTO topologyapplication (id, tenant_id, name, description, repository) 
        SELECT id, tenant_id, name, description, repository FROM topologyapplication_tmp
    """))

    session.execute(sa.text("""
        INSERT INTO topologyserviceapplication (service_id, application_id, tenant_id) 
        SELECT ts.id, tsa.application_id, ts.tenant_id FROM topologyserviceapplication_tmp as tsa
        JOIN topologyservice as ts ON tsa.service_id = ts.external_id
    """))

    session.execute(sa.text(f"""
        INSERT INTO topologyservicedependency (id, service_id, depends_on_service_id, updated_at, protocol, tenant_id) 
        SELECT {uuid_generation_func} as id, ts.id as service_id, ts_dep.id as depends_on_service_id, tsd.updated_at, tsd.protocol, ts.tenant_id
        FROM topologyservicedependency_tmp as tsd
        JOIN topologyservice as ts ON tsd.service_id = ts.external_id
        JOIN topologyservice as ts_dep ON tsd.depends_on_service_id = ts_dep.external_id
    """))


def transfer_data_back():
    session = Session(bind=op.get_bind())

    session.execute(sa.text("""
        INSERT INTO topologyservice (
            id, tenant_id, source_provider_id, repository, tags, service, environment, display_name, description, 
            team, email, slack, ip_address, mac_address, category, manufacturer, namespace, is_manual
        )
        SELECT external_id as id, tenant_id, source_provider_id, repository, tags, service, environment, display_name, description, 
        team, email, slack, ip_address, mac_address, category, manufacturer, namespace, is_manual 
        FROM topologyservice_tmp
    """))

    session.execute(sa.text("""
        INSERT INTO topologyapplication (id, tenant_id, name, description, repository) 
        SELECT id, tenant_id, name, description, repository FROM topologyapplication_tmp
    """))

    session.execute(sa.text("""
        INSERT INTO topologyserviceapplication (service_id, application_id) 
        SELECT ts.external_id, tsa.application_id FROM topologyserviceapplication_tmp as tsa
        JOIN topologyservice_tmp as ts ON tsa.service_id = ts.id
        
    """))

    session.execute(sa.text("""
        INSERT INTO topologyservicedependency (service_id, depends_on_service_id, updated_at, protocol) 
        SELECT ts.external_id, ts_dep.external_id, tsd.updated_at, tsd.protocol 
        FROM topologyservicedependency_tmp as tsd
        JOIN topologyservice_tmp as ts ON tsd.service_id = ts.id
        JOIN topologyservice_tmp as ts_dep ON tsd.depends_on_service_id = ts_dep.id
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
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.Integer(), nullable=True),
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
        sa.Column("service_id", sa.Uuid(), nullable=False),
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
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("depends_on_service_id", sa.Uuid(), nullable=False),
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

    # Let's do not drop this as backup for a while

    op.rename_table('topologyapplication_tmp', 'topologyapplication_backup')
    op.rename_table('topologyservice_tmp', 'topologyservice_backup')
    op.rename_table('topologyserviceapplication_tmp', 'topologyserviceapplication_backup')
    op.rename_table('topologyservicedependency_tmp', 'topologyservicedependency_backup')

    # But after some time we will need to execute this:

    # op.drop_table("topologyservicedependency_backup")
    # op.drop_table("topologyserviceapplication_backup")
    # op.drop_table("topologyapplication_backup")
    # op.drop_table("topologyservice_backup")


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
