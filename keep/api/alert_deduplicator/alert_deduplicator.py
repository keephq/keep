import copy
import hashlib
import json
import logging

from keep.api.core.config import config
from keep.api.core.db import (
    create_deduplication_event,
    get_all_dedup_ratio,
    get_all_deduplication_rules,
    get_custom_full_deduplication_rules,
    get_last_alert_hash_by_fingerprint,
    get_provider_distribution,
)
from keep.api.models.alert import AlertDto, DeduplicationRuleDto
from keep.api.models.db.alert import AlertDeduplicationRule
from keep.providers.providers_factory import ProvidersFactory


class AlertDeduplicator:

    def __init__(self, tenant_id):
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self.provider_distribution_enabled = config(
            "PROVIDER_DISTRIBUTION_ENABLED", cast=bool, default=True
        )

    def _apply_deduplication_rule(
        self, alert: AlertDto, rule: DeduplicationRuleDto
    ) -> bool:
        """
        Apply a deduplication rule to an alert.

        Gets an alert and a deduplication rule and apply the rule to the alert by:
        - removing the fields that should be ignored
        - calculating the hash
        - checking if the hash is already in the database
        - setting the isFullDuplicate or isPartialDuplicate flag
        """
        # remove the fields that should be ignored
        for field in rule.ignore_fields:
            alert = self._remove_field(field, alert)

        # calculate the hash
        alert_hash = hashlib.sha256(
            json.dumps(alert.dict(), default=str).encode()
        ).hexdigest()

        # Check if the hash is already in the database
        last_alert_hash_by_fingerprint = get_last_alert_hash_by_fingerprint(
            self.tenant_id, alert.fingerprint
        )
        # the hash is the same as the last alert hash by fingerprint - full deduplication
        if (
            last_alert_hash_by_fingerprint
            and last_alert_hash_by_fingerprint == alert_hash
        ):
            self.logger.info(
                "Alert is deduplicated",
                extra={
                    "alert_id": alert.id,
                    "tenant_id": self.tenant_id,
                },
            )
            alert.isFullDuplicate = True
        # it means that there is another alert with the same fingerprint but different hash
        # so its a deduplication
        elif last_alert_hash_by_fingerprint:
            self.logger.info(
                "Alert is partially deduplicated",
                extra={
                    "alert_id": alert.id,
                    "tenant_id": self.tenant_id,
                },
            )
            alert.isPartialDuplicate = True

        return alert

    def apply_deduplication(self, alert: AlertDto) -> bool:
        # IMPOTRANT NOTE TO SOMEONE WORKING ON THIS CODE:
        #   apply_deduplication runs AFTER _format_alert, so you can assume that alert fields are in the expected format.
        #   you can also safe to assume that alert.fingerprint is set by the provider itself

        # get only relevant rules
        rule = self.get_full_deduplication_rule(
            self.tenant_id, alert.provider_id, alert.provider_type
        )
        self.logger.debug(f"Applying deduplication rule {rule.id} to alert {alert.id}")
        alert = self._apply_deduplication_rule(rule, alert)
        self.logger.debug(f"Alert after deduplication rule {rule.id}: {alert}")
        if alert.isFullDuplicate or alert.isPartialDuplicate:
            create_deduplication_event(
                tenant_id=self.tenant_id,
                rule_id=rule.id,
                alert_fingerprint=alert.fingerprint,
                deduplication_type="full" if alert.isFullDuplicate else "partial",
            )
        return alert

    def _remove_field(self, field, alert: AlertDto) -> AlertDto:
        alert = copy.deepcopy(alert)
        field_parts = field.split(".")
        if len(field_parts) == 1:
            try:
                delattr(alert, field)
            except AttributeError:
                self.logger.warning(f"Failed to delete attribute {field} from alert")
        else:
            alert_attr = field_parts[0]
            d = copy.deepcopy(getattr(alert, alert_attr))
            for part in field_parts[1:-1]:
                d = d[part]
            del d[field_parts[-1]]
            setattr(alert, field_parts[0], d)
        return alert

    def get_full_deduplication_rule(
        self, tenant_id, provider_id, provider_type
    ) -> DeduplicationRuleDto:
        # try to get the rule from the database
        rule = get_custom_full_deduplication_rules(
            tenant_id, provider_id, provider_type
        )
        if rule:
            self.logger.debug(
                "Using custom deduplication rule",
                extra={
                    "provider_id": provider_id,
                    "provider_type": provider_type,
                    "tenant_id": tenant_id,
                },
            )
            return rule

        # no custom rule found, let's try to use the default one
        self.logger.debug(
            "Using default full deduplication rule",
            extra={
                "provider_id": provider_id,
                "provider_type": provider_type,
                "tenant_id": tenant_id,
            },
        )
        rule = self._get_default_full_deduplication_rule()
        return rule

    def _get_default_full_deduplication_rule(self) -> DeduplicationRuleDto:
        # just return a default deduplication rule with lastReceived field
        return AlertDeduplicationRule(
            fingerprint_fields=[],
            provider_id=None,
            full_deduplication=True,
            ignore_fields=["lastReceived"],
            priority=0,
        )

    def get_deduplications(self) -> list[DeduplicationRuleDto]:
        installed_providers = ProvidersFactory.get_installed_providers(self.tenant_id)
        installed_providers = [
            provider for provider in installed_providers if "alert" in provider.tags
        ]
        linked_providers = ProvidersFactory.get_linked_providers(self.tenant_id)
        providers = [*installed_providers, *linked_providers]

        default_deduplications = ProvidersFactory.get_default_deduplication_rules()
        default_deduplications_dict = {
            dd.provider_type: dd for dd in default_deduplications
        }

        custom_deduplications = get_all_deduplication_rules(self.tenant_id)
        custom_deduplications_dict = {
            rule.provider_id: rule for rule in custom_deduplications
        }

        final_deduplications = []
        for provider in providers:
            if provider.id not in custom_deduplications_dict:
                if provider.type not in default_deduplications_dict:
                    self.logger.warning(
                        f"Provider {provider.type} does not have a default deduplication"
                    )
                    continue

                default_deduplication = copy.deepcopy(
                    default_deduplications_dict[provider.type]
                )
                if provider.id:
                    default_deduplication.description = (
                        f"{default_deduplication.description} - {provider.id}"
                    )
                    default_deduplication.provider_id = provider.id

                final_deduplications.append(default_deduplication)
            else:
                final_deduplications.append(custom_deduplications_dict[provider.id])

        dedup_ratio = get_all_dedup_ratio(self.tenant_id)

        result = []
        for dedup in final_deduplications:
            dedup.ingested = dedup_ratio.get(
                (dedup.provider_id, dedup.provider_type), {}
            ).get("num_alerts", 0.0)
            dedup.dedup_ratio = dedup_ratio.get(
                (dedup.provider_id, dedup.provider_type), {}
            ).get("ratio", 0.0)
            result.append(dedup)

        if self.provider_distribution_enabled:
            providers_distribution = get_provider_distribution(self.tenant_id)
            for dedup in result:
                for pd in providers_distribution:
                    if pd == f"{dedup.provider_id}_{dedup.provider_type}":
                        distribution = providers_distribution[pd].get(
                            "alert_last_24_hours"
                        )
                        dedup.distribution = distribution
                        break

        return result
