"""Add anomaly_result table

Revision ID: 001_add_anomaly_result
Revises: xxx
Create Date: 2024-xx-xx

"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('anomalyresult',
                    sa.Column('id', sa.String(), nullable=False),
                    sa.Column('tenant_id', sa.String(), nullable=False),
                    sa.Column('alert_fingerprint', sa.String(), nullable=False),
                    sa.Column('is_anomaly', sa.Boolean(), nullable=False),
                    sa.Column('anomaly_score', sa.Float(), nullable=False),
                    sa.Column('confidence', sa.Float(), nullable=False),
                    sa.Column('explanation', sa.String(), nullable=False),
                    sa.Column('timestamp', sa.DateTime(), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index('ix_anomalyresult_tenant_id', 'anomalyresult', ['tenant_id'])
    op.create_index('ix_anomalyresult_alert_fingerprint', 'anomalyresult', ['alert_fingerprint'])


def downgrade():
    op.drop_table('anomalyresult')