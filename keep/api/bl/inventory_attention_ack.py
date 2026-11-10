"""Human ownership adapter called by Keep's existing authenticated status route."""
from fastapi import HTTPException
from sqlalchemy import select
from keep.api.models.db.incident import Incident
from keep.api.bl.inventory_attention import InventoryAttentionService, Policy
from keep.api.bl.inventory_attention_runtime import load_configuration


def acknowledge_owned_incident(engine, incident_id, status, actor, config=None):
    with engine.connect() as connection:
        row = connection.execute(select(Incident.tenant_id, Incident.fingerprint).where(
            Incident.id == incident_id)).first()
    if not row or row.tenant_id != actor.tenant_id or not (row.fingerprint or '').startswith('inventory:'):
        return False
    from keep.api.core.config import config as native_config
    if (native_config('AUTH_TYPE', default='noauth') not in ('auth0', 'keycloak', 'okta', 'onelogin', 'oidc', 'db')
            or native_config('KEEP_IMPERSONATION_ENABLED', default='false') == 'true'):
        raise HTTPException(403, 'Human ACK requires verified user authentication without API-key impersonation')
    if getattr(status, 'value', status) != 'acknowledged':
        raise HTTPException(409, 'Inventory closure requires a separately reviewed business-proof policy')
    config = config or load_configuration(actor.tenant_id)
    if not config:
        raise HTTPException(409, 'Inventory policy is inactive; ownership cannot be inferred')
    try:
        InventoryAttentionService(engine, actor.tenant_id, Policy(**config['policy'])).acknowledge(str(incident_id), actor)
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    return True
