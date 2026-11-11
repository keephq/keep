"""Protect reserved durable policy state from generic mutation APIs."""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from keep.api.bl.inventory_attention import OWNER
from keep.api.models.db.incident import Incident


def guard_enrichment(fingerprints, engine=None, tenant_id=None):
    if any(str(value).startswith('inventory-policy:') for value in fingerprints):
        raise HTTPException(409, 'Inventory policy state is reserved for its atomic service')
    if engine is not None:
        ids = []
        for value in fingerprints:
            try:
                ids.append(UUID(str(value)))
            except (ValueError, TypeError):
                pass
        if ids:
            guard_incidents(engine, tenant_id, ids)


def guard_incidents(engine, tenant_id, incident_ids):
    ids = []
    for value in incident_ids:
        try:
            ids.append(UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            continue
    if not ids:
        return
    with engine.connect() as connection:
        owned = connection.execute(select(Incident.id).where(
            Incident.tenant_id == tenant_id, Incident.id.in_(ids),
            Incident.fingerprint.in_([f"{OWNER}{value}" for value in ids]))).first()
    if owned:
        raise HTTPException(409, 'Inventory incidents require the dedicated human ACK or reviewed closure policy')
