"""Server-owned policy and bounded adapters for the native Inventory workflow."""
import json
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from keep.api.bl.inventory_attention import InventoryAttentionService, Policy, CHANNEL


def load_configuration(tenant_id):
    path = os.environ.get('INVENTORY_ATTENTION_POLICY_FILE')
    if not path:
        return None
    config = json.loads(Path(path).read_text()).get('tenants', {}).get(tenant_id)
    if not config or not config.get('policy', {}).get('enabled', False):
        return None
    Policy(**config['policy']).validate()
    targets = config.get('slack_targets', {})
    for role in ('primary', 'backup', 'incident_lead'):
        if not re.fullmatch(r'[UW][A-Z0-9]{8,}', targets.get(role, '')):
            raise ValueError('Enabled policy requires explicit Slack user paging destinations')
    if not config['policy'].get('reconciliation_seconds') or not config.get('fallback_provider_id'):
        raise ValueError('Enabled runtime policy requires reconciliation deadline and independent webhook provider')
    if config['fallback_provider_id'] == config.get('slack_provider_id'):
        raise ValueError('Independent route must differ from Slack')
    if not config.get('slack_provider_id'):
        raise ValueError('An installed OAuth Slack provider is required')
    return config


class NativeSlackNotifier:
    def __init__(self, provider, config, fallback_provider=None):
        if not provider.authentication_config.access_token or provider.authentication_config.webhook_url:
            raise ValueError('OAuth-only Slack installation required for real receipts')
        self.provider, self.config, self.fallback_provider = provider, config, fallback_provider

    def policy_binding(self):
        return {'channel': self.config['policy']['shared_channel'],
                'provider_id': self.config.get('slack_provider_id', 'fixture-provider'),
                'targets': dict(self.config['slack_targets']),
                'fallback_provider_id': self.config.get('fallback_provider_id'),
                'fallback_endpoint_digest': hashlib.sha256(str(self.fallback_provider.authentication_config.url).encode()).hexdigest() if self.fallback_provider is not None else None}

    def send_fallback(self, *, incident_id, text, idempotency_key):
        from keep.api.bl.inventory_attention import KnownNotDelivered
        if self.fallback_provider is None:
            raise KnownNotDelivered("Independent route unavailable")
        auth = self.fallback_provider.authentication_config
        # Native webhook _notify discards its result; _query preserves HTTP receipt
        # and the native bounded ten-second transport. No retry on ambiguous response.
        result = self.fallback_provider._query(
            url=auth.url, method=auth.method,
            http_basic_authentication_username=auth.http_basic_authentication_username,
            http_basic_authentication_password=auth.http_basic_authentication_password,
            api_key=auth.api_key, headers=auth.headers,
            body={"incident_id": incident_id, "claim_id": idempotency_key, "evidence": text})
        body = result.get("body", {})
        if not result.get("status") or not isinstance(body, dict) or not body.get("receipt_id"):
            raise RuntimeError("Independent receiver did not acknowledge durable acceptance")
        return str(body["receipt_id"])

    def send(self, *, transition, text, thread_ts, idempotency_key):
        # Evidence is plain text; only approved configuration can create mentions.
        blocks = [{'type': 'section', 'text': {'type': 'plain_text', 'text': text[:2900]}}]
        targets = self.config['slack_targets']
        mention = '' if transition == 'initial' else '<@' + targets[transition] + '>'
        if transition == 'backup':
            mention += ' <@' + targets['incident_lead'] + '>'
        if mention:
            blocks.insert(0, {'type': 'section', 'text': {'type': 'mrkdwn', 'text': mention}})
        receipt = self.provider._notify(
            message='Inventory attention', blocks=blocks,
            channel=self.config['policy']['shared_channel'],
            thread_timestamp=thread_ts or '', request_timeout=5,
        )
        return receipt['slack_timestamp']


def signal_from_alert(alert):
    # Keep Grafana formatter lifts labels; annotations remain nested.
    if isinstance(alert, str):
        if len(alert) > 65536:
            raise ValueError("Alert exceeds bounded input")
        alert = json.loads(alert)
    if not isinstance(alert, dict):
        raise ValueError("Alert must be a JSON object")
    if alert.get('inventory_attention_owner') != 'inventory-attention-v1':
        raise ValueError('Alert is not opted into Inventory attention')
    annotations = alert.get('annotations') if isinstance(alert.get('annotations'), dict) else {}
    observed = alert.get('inventory_observed_at') or annotations.get('inventory_observed_at') or alert.get('lastReceived')
    # lastReceived is Keep intake time, never acceptance or durable progress.
    if isinstance(observed, str) and not observed.replace('.', '', 1).isdigit():
        observed = datetime.fromisoformat(observed.replace('Z', '+00:00')).timestamp()
    kind = alert.get('inventory_kind', 'parent_unknown')
    evaluation_error = bool(annotations.get('Error') or annotations.get('error'))
    truncated = alert.get('coverage') == 'truncated'
    if evaluation_error or truncated or alert.get('alertname') in ('DatasourceNoData', 'DatasourceError'):
        kind = 'coverage_unknown'
    elif alert.get('status') == 'resolved':
        kind = 'recovery'
    return dict(channel=CHANNEL, kind=kind,
                observed_at=observed, event_id=alert.get('fingerprint'),
                job_uuid=alert.get('job_uuid'), graph_uuid=alert.get('graph_uuid'),
                operation_id=alert.get('operation_id'), source_fingerprint=alert.get('fingerprint'),
                evidence={'source': 'grafana-postgresql', 'captured_at': observed,
                          'queue_state': 'unknown' if evaluation_error else alert.get('queue_state', 'unknown'),
                          'business_state': 'unknown' if evaluation_error else alert.get('business_state', 'unknown'),
                          'truncated': alert.get('coverage', 'unknown'),
                          'completeness': ('datasource_or_evaluation_error; business_success_not_proven' if evaluation_error else 'detector_result_truncated; business_success_not_proven' if truncated else 'retained_jobs_only; source_order_unknown; business_success_not_proven')})


class InventoryWorkflow:
    """Same entry point used by the native provider and isolated circuit fixtures."""
    def __init__(self, engine, tenant_id, config, notifier, clock=None):
        kwargs = {} if clock is None else {'clock': clock}
        self.service = InventoryAttentionService(engine, tenant_id, Policy(**config['policy']), **kwargs)
        self.notifier = notifier

    def run(self, operation, alert=None):
        if not self.service.policy.enabled:
            return {'status': 'disabled'}
        if operation == 'sweep':
            return self.service.sweep(self.notifier)
        if operation != 'ingest':
            raise ValueError('Only ingest and sweep are available; recovery is excluded')
        state = self.service.ingest(signal_from_alert(alert))
        return self.service.dispatch(state['incident_id'], self.notifier)


def filter_inactive_inventory(tenant_id, event):
    """Drop only the reserved candidate protocol before native ingestion I/O.

    Supports Grafana batches, native batches and already formatted DTOs. Existing
    Inventory alerts without the opt-in owner and all other alerts are untouched.
    Disabled inputs are deliberately not persisted as raw/error alerts.
    """
    def owned(value):
        if isinstance(value, dict):
            return (value.get('inventory_attention_owner') == 'inventory-attention-v1'
                    or (value.get('labels') if isinstance(value.get('labels'), dict) else {}).get('inventory_attention_owner') == 'inventory-attention-v1')
        return getattr(value, 'inventory_attention_owner', None) == 'inventory-attention-v1'

    envelope = isinstance(event, dict) and isinstance(event.get('alerts'), list)
    batch = event['alerts'] if envelope else event if isinstance(event, list) else [event]
    if not any(owned(item) for item in batch):
        return event
    try:
        enabled = load_configuration(tenant_id) is not None
    except (ValueError, OSError, TypeError):
        enabled = False  # Fail closed for owned inputs; legacy traffic still passes.
    if enabled:
        return event
    remaining = [item for item in batch if not owned(item)]
    if not remaining:
        return None
    if envelope:
        return {**event, 'alerts': remaining}
    return remaining if isinstance(event, list) else remaining[0]
