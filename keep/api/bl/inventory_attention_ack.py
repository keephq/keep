"""Human ownership adapter called by Keep's existing authenticated status route."""
from fastapi import HTTPException
from sqlalchemy import select
from keep.api.models.db.incident import Incident
from keep.api.bl.inventory_attention import InventoryAttentionService, Policy, OWNER
from keep.api.bl.inventory_attention_runtime import load_configuration


def acknowledge_owned_incident(engine, incident_id, status, actor, config=None):
    with engine.connect() as connection:
        row = connection.execute(select(Incident.tenant_id, Incident.fingerprint).where(
            Incident.id == incident_id)).first()
    if not row or row.tenant_id != actor.tenant_id or row.fingerprint != f"{OWNER}{incident_id}":
        return False
    from keep.api.core.config import config as native_config
    if (native_config('AUTH_TYPE', default='noauth') not in ('auth0', 'keycloak', 'okta', 'onelogin', 'oidc', 'db')
            or native_config('KEEP_IMPERSONATION_ENABLED', default='false') == 'true'):
        raise HTTPException(403, 'Human ACK requires verified user authentication without API-key impersonation')
    if getattr(status, 'value', status) != 'acknowledged':
        raise HTTPException(409, 'Inventory closure requires a separately reviewed business-proof policy')
    config = config or load_configuration(actor.tenant_id)
    if not config or not config.get('policy', {}).get('enabled'):
        raise HTTPException(409, 'Inventory policy is inactive; ownership cannot be inferred')
    try:
        InventoryAttentionService(engine, actor.tenant_id, Policy(**config['policy'])).acknowledge(str(incident_id), actor)
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    return True


def human_lifecycle_action(engine, incident_id, actor, operation, payload, config=None):
    from keep.api.core.config import config as native_config
    if (native_config('AUTH_TYPE', default='noauth') not in ('auth0', 'keycloak', 'okta', 'onelogin', 'oidc', 'db')
            or native_config('KEEP_IMPERSONATION_ENABLED', default='false') == 'true'):
        raise HTTPException(403, 'Verified human authentication without impersonation required')
    config = config or load_configuration(actor.tenant_id)
    if not config or not config.get('policy', {}).get('enabled'):
        raise HTTPException(409, 'Inventory policy is inactive')
    service = InventoryAttentionService(engine, actor.tenant_id, Policy(**config['policy']))
    try:
        if operation == 'resolve':
            return service.resolve(str(incident_id), actor, expected_revision=payload.get('expected_revision'), evidence=payload.get('evidence'))
        if operation == 'reopen':
            return service.reopen(str(incident_id), actor, expected_revision=payload.get('expected_revision'), reason=payload.get('reason'))
        raise ValueError('Unsupported human action')
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    except (ValueError, LookupError) as error:
        raise HTTPException(409, str(error)) from error
