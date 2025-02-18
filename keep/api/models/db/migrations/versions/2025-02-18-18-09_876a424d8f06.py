"""Extend dismissed enrichments with SUPPRESSED status

Revision ID: 876a424d8f06
Revises: 8176d7153747
Create Date: 2025-02-18 18:09:40.656808

"""

from alembic import op
from sqlalchemy import and_, null
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session

from keep.api.core.db_utils import get_json_extract_field
from keep.api.models.alert import AlertStatus
from keep.api.models.db.alert import AlertEnrichment, Alert

# revision identifiers, used by Alembic.
revision = "876a424d8f06"
down_revision = "8176d7153747"
branch_labels = None
depends_on = None

def populate_db():
    session = Session(op.get_bind())

    dismissed_field = get_json_extract_field(session, AlertEnrichment.enrichments, "dismissed")
    status_field = get_json_extract_field(session, AlertEnrichment.enrichments, "status")

    enrichments = session.query(AlertEnrichment).filter(
        and_(
            dismissed_field.in_(['true', 'True']),
            status_field.is_(null())
        )
    ).all()

    for enrichment in enrichments:
        enrichment.enrichments['status'] = AlertStatus.SUPPRESSED.value
        flag_modified(enrichment, "enrichments")
        session.add(enrichment)
    session.commit()

def upgrade() -> None:
    populate_db()


def downgrade() -> None:
    pass
