"""Add fields for prepopulated data from alerts

Revision ID: 67f1efb93c99
Revises: dcbd2873dcfd
Create Date: 2024-07-25 17:13:04.428633

"""

import sqlalchemy as sa
from alembic import op
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import OperationalError

from keep.api.models.db.alert import Incident

# revision identifiers, used by Alembic.
revision = "67f1efb93c99"
down_revision = "dcbd2873dcfd"
branch_labels = None
depends_on = None


class AlertDtoLocal(BaseModel):
    service: str | None = None
    source: list[str] | None = []


def populate_db(session):

    # Todo fix: This doesn't work on further revisions after Incident is changed. Remove exception handling.
    incidents = session.query(Incident).options(joinedload(Incident.alerts)).all()

    for incident in incidents:
        alerts_dto = [AlertDtoLocal(**alert.event) for alert in incident.alerts]

        incident.sources = list(
            set([source for alert_dto in alerts_dto for source in alert_dto.source])
        )
        incident.affected_services = list(
            set([alert.service for alert in alerts_dto if alert.service is not None])
        )
        incident.alerts_count = len(incident.alerts)
        session.add(incident)
    session.commit()


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("incident", sa.Column("affected_services", sa.JSON(), nullable=True))
    op.add_column("incident", sa.Column("sources", sa.JSON(), nullable=True))
    op.add_column("incident", sa.Column("alerts_count", sa.Integer(), nullable=False, server_default="0"))

    session = Session(op.get_bind())
    try:
        populate_db(session)
    except OperationalError as e:
        print(f"Failed to populate db but still processing: {e}")

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("incident", "alerts_count")
    op.drop_column("incident", "sources")
    op.drop_column("incident", "affected_services")
    # ### end Alembic commands ###
