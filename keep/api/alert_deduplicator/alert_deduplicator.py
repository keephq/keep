import copy
import hashlib
import json
import logging

from keep.api.core.config import config
from keep.api.core.db import (
    create_deduplication_event,
    create_deduplication_rule,
    delete_deduplication_rule,
    get_alerts_fields,
    get_all_dedup_ratio,
    get_all_deduplication_rules,
    get_custom_full_deduplication_rules,
    get_last_alert_hash_by_fingerprint,
    get_provider_distribution,
    update_deduplication_rule,
)
from keep.api.models.alert import (
    AlertDto,
    DeduplicationRuleDto,
    DeduplicationRuleRequestDto,
)
from keep.providers.providers_factory import ProvidersFactory
from keep.searchengine.searchengine import SearchEngine

DEFAULT_RULE_UUID = "00000000-0000-0000-0000-000000000000"


class AlertDeduplicator:

    def __init__(self, tenant_id):
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self.provider_distribution_enabled = config(
            "PROVIDER_DISTRIBUTION_ENABLED", cast=bool, default=True
        )
        self.search_engine = SearchEngine(self.tenant_id)

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
        # we don't want to remove fields from the original alert
        alert_copy = copy.deepcopy(alert)
        # remove the fields that should be ignored
        for field in rule.ignore_fields:
            alert_copy = self._remove_field(field, alert_copy)

        # calculate the hash
        alert_hash = hashlib.sha256(
            json.dumps(alert_copy.dict(), default=str).encode()
        ).hexdigest()
        alert.alert_hash = alert_hash
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
                    "rule_id": rule.id,
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
            self.tenant_id, alert.providerId, alert.providerType
        )
        self.logger.debug(
            "Applying deduplication rule to alert",
            extra={
                "rule_id": rule.id,
                "alert_id": alert.id,
            },
        )
        alert = self._apply_deduplication_rule(alert, rule)
        self.logger.debug(
            "Alert after deduplication rule applied",
            extra={
                "rule_id": rule.id,
                "alert_id": alert.id,
                "is_full_duplicate": alert.isFullDuplicate,
                "is_partial_duplicate": alert.isPartialDuplicate,
            },
        )
        if alert.isFullDuplicate or alert.isPartialDuplicate:
            # create deduplication event
            create_deduplication_event(
                tenant_id=self.tenant_id,
                deduplication_rule_id=rule.id,
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
        return DeduplicationRuleDto(
            id=DEFAULT_RULE_UUID,
            name="Keep Full Deduplication Rule",
            description="Keep Full Deduplication Rule",
            default=True,
            distribution=[],
            fingerprint_fields=[],
            provider_type="keep",
            provider_id=None,
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
        )

    def get_deduplications(self) -> list[DeduplicationRuleDto]:
        # get all providers
        installed_providers = ProvidersFactory.get_installed_providers(self.tenant_id)
        installed_providers = [
            provider for provider in installed_providers if "alert" in provider.tags
        ]
        # get all linked providers
        linked_providers = ProvidersFactory.get_linked_providers(self.tenant_id)
        providers = [*installed_providers, *linked_providers]

        # get default deduplication rules
        default_deduplications = ProvidersFactory.get_default_deduplication_rules()
        default_deduplications_dict = {
            dd.provider_type: dd for dd in default_deduplications
        }
        # get custom deduplication rules
        custom_deduplications = get_all_deduplication_rules(self.tenant_id)
        custom_deduplications_dict = {
            rule.provider_id: rule for rule in custom_deduplications
        }
        # get the "catch all" full deduplication rule
        catch_all_full_deduplication = self._get_default_full_deduplication_rule()

        # calculate the deduplciations
        # if a provider has custom deduplication rule, use it
        # else, use the default deduplication rule of the provider
        final_deduplications = [catch_all_full_deduplication]
        for provider in providers:
            # if the provider doesn't have a deduplication rule, use the default one
            if provider.id not in custom_deduplications_dict:
                # no default deduplication rule found [if provider doesn't have FINGERPRINT_FIELDS]
                if provider.type not in default_deduplications_dict:
                    self.logger.warning(
                        f"Provider {provider.type} does not have a default deduplication"
                    )
                    continue

                # create a copy of the default deduplication rule
                default_deduplication = copy.deepcopy(
                    default_deduplications_dict[provider.type]
                )
                # copy the provider id to the description
                if provider.id:
                    default_deduplication.description = (
                        f"{default_deduplication.description} - {provider.id}"
                    )
                    default_deduplication.provider_id = provider.id
                # set the provider type
                final_deduplications.append(default_deduplication)
            # else, just use the custom deduplication rule
            else:
                final_deduplications.append(custom_deduplications_dict[provider.id])

        # now calculate some statistics
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

    def get_deduplication_fields(self) -> list[str]:
        fields = get_alerts_fields(self.tenant_id)

        fields_per_provider = {}
        for field in fields:
            provider_type = field.provider_type if field.provider_type else "null"
            provider_id = field.provider_id if field.provider_id else "null"
            key = f"{provider_type}_{provider_id}"
            if key not in fields_per_provider:
                fields_per_provider[key] = []
            fields_per_provider[key].append(field.field_name)

        return fields_per_provider

    def create_deduplication_rule(
        self, rule: DeduplicationRuleRequestDto, created_by: str
    ) -> DeduplicationRuleDto:
        # Use the db function to create a new deduplication rule
        new_rule = create_deduplication_rule(
            tenant_id=self.tenant_id,
            name=rule.name,
            description=rule.description,
            provider_id=rule.provider_id,
            provider_type=rule.provider_type,
            created_by=created_by,
            enabled=True,
            fingerprint_fields=rule.fingerprint_fields,
            full_deduplication=rule.full_deduplication,
            ignore_fields=rule.ignore_fields or [],
            priority=0,
        )

        return new_rule

    def update_deduplication_rule(
        self, rule_id: str, rule: DeduplicationRuleRequestDto, updated_by: str
    ) -> DeduplicationRuleDto:
        # Use the db function to update an existing deduplication rule
        updated_rule = update_deduplication_rule(
            rule_id=rule_id,
            tenant_id=self.tenant_id,
            name=rule.name,
            description=rule.description,
            provider_id=rule.provider_id,
            provider_type=rule.provider_type,
            last_updated_by=updated_by,
            enabled=True,
            fingerprint_fields=rule.fingerprint_fields,
            full_deduplication=rule.full_deduplication,
            ignore_fields=rule.ignore_fields or [],
            priority=0,
        )

        return updated_rule

    def delete_deduplication_rule(self, rule_id: str) -> bool:
        # Use the db function to delete a deduplication rule
        success = delete_deduplication_rule(rule_id=rule_id, tenant_id=self.tenant_id)

        return success
