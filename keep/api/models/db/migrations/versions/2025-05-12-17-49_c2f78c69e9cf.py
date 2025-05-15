"""Recalculate alerts_count for incidents

Revision ID: c2f78c69e9cf
Revises: 7b687c555318
Create Date: 2025-05-12 17:49:09.779088

"""

from collections import defaultdict

from alembic import op
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import count

from keep.api.models.db.alert import LastAlertToIncident
from keep.api.models.db.helpers import NULL_FOR_DELETED_AT
from keep.api.models.db.incident import Incident

# revision identifiers, used by Alembic.
revision = "c2f78c69e9cf"
down_revision = "7b687c555318"
branch_labels = None
depends_on = None


def upgrade() -> None:
    session = Session(op.get_bind())
    counts = session.execute(
        select(
        count(LastAlertToIncident.fingerprint), LastAlertToIncident.incident_id
        )
        .where(LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT)
        .group_by(LastAlertToIncident.incident_id)
    ).all()
    counts_per_incident = defaultdict(int)
    for count_, incident_id in counts:
        counts_per_incident[incident_id] = count_

    incident_ids = session.execute(select(Incident.id)).scalars().all()

    for incident_id in incident_ids:
        session.execute(
            update(Incident)
            .where(Incident.id == incident_id)
            .values(alerts_count=counts_per_incident.get(incident_id, 0))
        )
        session.commit()

def downgrade() -> None:
    pass
