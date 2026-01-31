import copy
import hashlib
import json
import logging
import uuid
from typing import Any

from fastapi import HTTPException

from keep.api.core.config import config
from keep.api.core.db import (
    create_deduplication_event,
    create_deduplication_rule,
    delete_deduplication_rule,
    get_alerts_fields,
    get_all_deduplication_rules,
    get_all_deduplication_stats,
    get_custom_deduplication_rule,
    get_deduplication_rule_by_id,
    get_last_alert_hashes_by_fingerprints,
    update_deduplication_rule,
)
from keep.api.models.alert import (
    AlertDto,
    DeduplicationRuleDto,
    DeduplicationRuleRequestDto,
)
from keep.providers.providers_factory import ProvidersFactory

DEFAULT_RULE_UUID = "00000000-0000-0000-0000-000000000000"


class AlertDeduplicator:
    DEDUPLICATION_DISTRIBUTION_ENABLED = config(
        "KEEP_DEDUPLICATION_DISTRIBUTION_ENABLED", cast=bool, default=True
    )
    CUSTOM_DEDUPLICATION_DISTRIBUTION_ENABLED = config(
        "KEEP_CUSTOM_DEDUPLICATION_ENABLED", cast=bool, default=True
    )

    def __init__(self, tenant_id):
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id

    # ----------------------------
    # Core deduplication operations
    # ----------------------------

    # IMPORTANT NOTE TO SOMEONE WORKING ON THIS CODE:
    #   apply_deduplication runs AFTER _format_alert, so you can assume that alert fields are in the expected format.
    #   you are also safe to assume that alert.fingerprint is set by the provider itself

    def apply_deduplication(
        self,
        alert: AlertDto,
        rules: list["DeduplicationRuleDto"] | None = None,
        last_alert_fingerprint_to_hash: dict[str, str] | None = None,
    ) -> AlertDto:
        # get only relevant rules
        rules = rules or self.get_deduplication_rules(
            self.tenant_id, alert.providerId, alert.providerType
        )

        for rule in rules:
            self.logger.debug(
                "Applying deduplication rule to alert",
                extra={"rule_id": rule.id, "alert_id": alert.id},
            )

            alert = self._apply_deduplication_rule(alert, rule, last_alert_fingerprint_to_hash)

            self.logger.debug(
                "Alert after deduplication rule applied",
                extra={
                    "rule_id": rule.id,
                    "alert_id": alert.id,
                    "is_full_duplicate": alert.isFullDuplicate,
                    "is_partial_duplicate": alert.isPartialDuplicate,
                },
            )

            if AlertDeduplicator.DEDUPLICATION_DISTRIBUTION_ENABLED:
                if alert.isFullDuplicate or alert.isPartialDuplicate:
                    create_deduplication_event(
                        tenant_id=self.tenant_id,
                        deduplication_rule_id=rule.id,
                        deduplication_type=("full" if alert.isFullDuplicate else "partial"),
                        provider_id=alert.providerId,
                        provider_type=alert.providerType,
                    )
                    break
                else:
                    create_deduplication_event(
                        tenant_id=self.tenant_id,
                        deduplication_rule_id=rule.id,
                        deduplication_type="none",
                        provider_id=alert.providerId,
                        provider_type=alert.providerType,
                    )

        return alert

    def _apply_deduplication_rule(
        self,
        alert: AlertDto,
        rule: DeduplicationRuleDto,
        last_alert_fingerprint_to_hash: dict[str, str] | None = None,
    ) -> AlertDto:
        """
        Apply a deduplication rule to an alert by:
        - removing ignored fields
        - computing a stable hash
        - comparing against last stored hash per fingerprint
        - setting isFullDuplicate / isPartialDuplicate
        """

        # we don't want to remove fields from the original alert
        alert_copy = copy.deepcopy(alert)

        # remove the fields that should be ignored (safe removal)
        for field in rule.ignore_fields:
            alert_copy = self._remove_field_safe(field, alert_copy)

        # compute hash deterministically
        alert_hash = self._compute_alert_hash(alert_copy)
        alert.alert_hash = alert_hash

        # Pull last hash from provided cache, else DB
        last_alerts_hash_by_fingerprint = (
            last_alert_fingerprint_to_hash
            or get_last_alert_hashes_by_fingerprints(self.tenant_id, [alert.fingerprint])
        )

        last_hash = last_alerts_hash_by_fingerprint.get(alert.fingerprint)

        # Full duplicate: same fingerprint + same hash
        if last_hash and last_hash == alert_hash:
            self.logger.info(
                "Alert is a full duplicate",
                extra={"alert_id": alert.id, "rule_id": rule.id, "tenant_id": self.tenant_id},
            )
            alert.isFullDuplicate = True

        # Partial: same fingerprint existed, but payload differs
        elif last_hash:
            self.logger.info(
                "Alert has same fingerprint but changed payload (partial duplicate)",
                extra={"alert_id": alert.id, "tenant_id": self.tenant_id},
            )
            alert.isPartialDuplicate = True

        else:
            self.logger.debug(
                "Alert is not a duplicate",
                extra={
                    "alert_id": alert.id,
                    "fingerprint": alert.fingerprint,
                    "tenant_id": self.tenant_id,
                },
            )

        return alert

    def _compute_alert_hash(self, alert: AlertDto) -> str:
        """
        Compute a deterministic SHA256 hash of the alert model.
        Uses sorted keys and default=str to avoid serialization crashes.
        (If you later want stricter hashing, remove default=str and fix upstream types.)
        """
        payload = alert.dict()
        raw = json.dumps(payload, default=str, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ----------------------------
    # Safe field removal utilities
    # ----------------------------

    def _remove_field_safe(self, field: str, alert: AlertDto) -> AlertDto:
        """
        Remove a field from the alert safely.
        Supports dotted paths like 'labels.foo.bar'.
        Does NOT raise if the field/path doesn't exist.
        """
        alert = copy.deepcopy(alert)
        parts = field.split(".")

        # top-level attribute
        if len(parts) == 1:
            try:
                delattr(alert, field)
            except AttributeError:
                # Not present: ignore silently (debug-level optional)
                self.logger.debug("Ignore field missing on alert (top-level)", extra={"field": field})
            return alert

        root_attr = parts[0]
        try:
            obj = copy.deepcopy(getattr(alert, root_attr))
        except AttributeError:
            self.logger.debug("Ignore field root attr missing on alert", extra={"field": field})
            return alert

        # Only dict-like navigation is supported here (as original code implied)
        if not isinstance(obj, dict):
            self.logger.debug(
                "Ignore field root attr is not a dict; skipping nested delete",
                extra={"field": field, "root_attr": root_attr},
            )
            return alert

        d: Any = obj
        for key in parts[1:-1]:
            if not isinstance(d, dict) or key not in d:
                # Path doesn't exist
                self.logger.debug("Ignore field path missing; skipping", extra={"field": field})
                return alert
            d = d[key]

        last_key = parts[-1]
        if isinstance(d, dict) and last_key in d:
            del d[last_key]
        else:
            self.logger.debug("Ignore field leaf missing; skipping", extra={"field": field})
            return alert

        setattr(alert, root_attr, obj)
        return alert

    # ----------------------------
    # Rule retrieval logic (unchanged behavior)
    # ----------------------------

    def get_deduplication_rules(
        self, tenant_id, provider_id, provider_type
    ) -> list[DeduplicationRuleDto]:
        if not provider_type:
            provider_type = "keep"

        rule = (
            get_custom_deduplication_rule(tenant_id, provider_id, provider_type)
            if AlertDeduplicator.CUSTOM_DEDUPLICATION_DISTRIBUTION_ENABLED
            else None
        )

        if not rule:
            self.logger.debug(
                "No custom deduplication rule found, using default full deduplication rule",
                extra={"provider_id": provider_id, "provider_type": provider_type, "tenant_id": tenant_id},
            )
            return [self._get_default_full_deduplication_rule(provider_id, provider_type)]

        self.logger.debug(
            "Using custom deduplication rules",
            extra={"provider_id": provider_id, "provider_type": provider_type, "tenant_id": tenant_id},
        )

        if rule.full_deduplication:
            return [rule]

        self.logger.info(
            "No full deduplication rule found, assigning default full deduplication rule ignore fields"
        )
        default_full_dedup_rule = self._get_default_full_deduplication_rule(provider_id, provider_type)
        rule.ignore_fields = default_full_dedup_rule.ignore_fields
        return [rule]

    def _generate_uuid(self, provider_id, provider_type):
        namespace_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, "keephq.dev")
        if not provider_id and provider_type and provider_type.lower() == "keep":
            provider_type = None
        return str(uuid.uuid5(namespace_uuid, f"{provider_id}_{provider_type}"))

    def _get_default_full_deduplication_rule(
        self, provider_id, provider_type
    ) -> DeduplicationRuleDto:
        generated_uuid = self._generate_uuid(provider_id, provider_type)

        if not provider_type:
            provider_type = "keep"

        return DeduplicationRuleDto(
            id=generated_uuid,
            name=f"{provider_type} default deduplication rule",
            description=f"{provider_type} default deduplication rule",
            default=True,
            distribution=[{"hour": i, "number": 0} for i in range(24)],
            fingerprint_fields=[],
            provider_type=provider_type or "keep",
            provider_id=provider_id,
            full_deduplication=True,
            ignore_fields=["lastReceived"],
            priority=0,
            last_updated=None,
            last_updated_by=None,
            created_at=None,
            created_by=None,
            ingested=0,
            dedup_ratio=0.0,
            enabled=True,
            is_provisioned=False,
        )

    # ----------------------------
    # Stats distribution key compatibility fix
    # ----------------------------

    def _get_stats_distribution(self, stats: dict) -> Any:
        """
        Backward/forward compatible access for distribution keys.
        Some code paths use 'alerts_last_24_hours', others used 'alert_last_24_hours'.
        """
        return stats.get("alerts_last_24_hours") or stats.get("alert_last_24_hours")

    # NOTE: In your existing get_deduplications() method, replace any:
    #   stats.get("alert_last_24_hours")
    # with:
    #   self._get_stats_distribution(stats)