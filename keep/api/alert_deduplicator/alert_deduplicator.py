import copy
import hashlib
import json
import logging
import uuid

from keep.api.core.config import config
from keep.api.core.db import (
    create_deduplication_event,
    create_deduplication_rule,
    delete_deduplication_rule,
    get_alerts_fields,
    get_all_alerts_by_providers,
    get_all_deduplication_rules,
    get_all_deduplication_stats,
    get_custom_deduplication_rules,
    get_last_alert_hash_by_fingerprint,
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
        rules = self.get_deduplication_rules(
            self.tenant_id, alert.providerId, alert.providerType
        )

        for rule in rules:
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
                    provider_id=alert.providerId,
                    provider_type=alert.providerType,
                )
                # we don't need to check the other rules
                break
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

    def get_deduplication_rules(
        self, tenant_id, provider_id, provider_type
    ) -> DeduplicationRuleDto:
        # try to get the rule from the database
        rules = get_custom_deduplication_rules(tenant_id, provider_id, provider_type)

        if not rules:
            self.logger.debug(
                "No custom deduplication rules found, using deafult full deduplication rule",
                extra={
                    "provider_id": provider_id,
                    "provider_type": provider_type,
                    "tenant_id": tenant_id,
                },
            )
            rule = self._get_default_full_deduplication_rule(provider_id, provider_type)
            return [rule]

        # else, return the custom rules
        self.logger.debug(
            "Using custom deduplication rules",
            extra={
                "provider_id": provider_id,
                "provider_type": provider_type,
                "tenant_id": tenant_id,
            },
        )
        #
        # check that at least one of them is full deduplication rule
        full_deduplication_rules = [rule for rule in rules if rule.full_deduplication]
        # if full deduplication rule found, return the rules
        if full_deduplication_rules:
            return rules

        # if not, assign them the default full deduplication rule ignore fields
        self.logger.info(
            "No full deduplication rule found, assigning default full deduplication rule ignore fields"
        )
        default_full_dedup_rule = self._get_default_full_deduplication_rule(
            provider_id=provider_id, provider_type=provider_type
        )
        for rule in rules:
            if not rule.full_deduplication:
                self.logger.debug(
                    "Assigning default full deduplication rule ignore fields",
                )
                rule.ignore_fields = default_full_dedup_rule.ignore_fields
        return rules

    def _get_default_full_deduplication_rule(
        self, provider_id, provider_type
    ) -> DeduplicationRuleDto:
        # this is a way to generate a unique uuid for the default deduplication rule per (provider_id, provider_type)
        namespace_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, "keephq.dev")
        generated_uuid = str(
            uuid.uuid5(namespace_uuid, f"{provider_id}_{provider_type}")
        )

        # just return a default deduplication rule with lastReceived field
        if not provider_type:
            provider_type = "keep"

        return DeduplicationRuleDto(
            id=generated_uuid,
            name=f"{provider_type} default deduplication rule",
            description=f"{provider_type} default deduplication rule",
            default=True,
            distribution=[],
            fingerprint_fields=[],  # ["fingerprint"], # this is fallback
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
        # cast to dto
        custom_deduplications_dto = [
            DeduplicationRuleDto(
                id=str(rule.id),
                name=rule.name,
                description=rule.description,
                default=False,
                distribution=[{"hour": i, "number": 0} for i in range(24)],
                fingerprint_fields=rule.fingerprint_fields,
                provider_type=rule.provider_type,
                provider_id=rule.provider_id,
                full_deduplication=rule.full_deduplication,
                ignore_fields=rule.ignore_fields,
                priority=rule.priority,
                last_updated=str(rule.last_updated),
                last_updated_by=rule.last_updated_by,
                created_at=str(rule.created_at),
                created_by=rule.created_by,
                ingested=0,
                dedup_ratio=0.0,
                enabled=rule.enabled,
            )
            for rule in custom_deduplications
        ]

        custom_deduplications_dict = {}
        for rule in custom_deduplications_dto:
            key = f"{rule.provider_type}_{rule.provider_id}"
            if key not in custom_deduplications_dict:
                custom_deduplications_dict[key] = []
            custom_deduplications_dict[key].append(rule)

        # get the "catch all" full deduplication rule
        catch_all_full_deduplication = self._get_default_full_deduplication_rule(
            provider_id=None, provider_type=None
        )

        # calculate the deduplciations
        # if a provider has custom deduplication rule, use it
        # else, use the default deduplication rule of the provider
        final_deduplications = [catch_all_full_deduplication]
        for provider in providers:
            # if the provider doesn't have a deduplication rule, use the default one
            key = f"{provider.type}_{provider.id}"
            if key not in custom_deduplications_dict:
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
                final_deduplications += custom_deduplications_dict[key]

        # now calculate some statistics
        alerts_by_provider_stats = get_all_alerts_by_providers(self.tenant_id)
        deduplication_stats = get_all_deduplication_stats(self.tenant_id)

        result = []
        for dedup in final_deduplications:
            key = f"{dedup.provider_type}_{dedup.provider_id}"
            dedup.ingested = alerts_by_provider_stats[key].get("num_alerts", 0)
            if dedup.ingested == 0:
                dedup.dedup_ratio = 0.0
            # this shouldn't happen, only in backward compatibility or some bug that dedup events are not created
            elif key not in deduplication_stats:
                self.logger.warning(f"Provider {key} does not have deduplication stats")
                dedup.dedup_ratio = 0.0
            elif deduplication_stats[key].get("dedup_count", 0) == 0:
                dedup.dedup_ratio = 0.0
            else:
                dedup.dedup_ratio = (
                    deduplication_stats[key].get("dedup_count")
                    / (deduplication_stats[key].get("dedup_count") + dedup.ingested)
                ) * 100
                dedup.distribution = deduplication_stats[key].get(
                    "alerts_last_24_hours"
                )
            result.append(dedup)

        if self.provider_distribution_enabled:
            for dedup in result:
                for pd, stats in deduplication_stats.items():
                    if pd == f"{dedup.provider_id}_{dedup.provider_type}":
                        distribution = stats.get("alert_last_24_hours")
                        dedup.distribution = distribution
                        break

        # sort providers to have enabled first
        result = sorted(result, key=lambda x: x.default, reverse=True)

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
